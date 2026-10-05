#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"
require "date"
require "uri"
require "yaml"

ROOT = Pathname.new(__dir__).parent.expand_path
ERRORS = []

REQUIRED = %w[
  AGENTS.md
  README.md
  CHANGELOG.md
  LICENSE
  concepts.yaml
  sources.yaml
  signals/common.yaml
  providers/openai/signals.yaml
  .agents/skills/standard/SKILL.md
  skills/pact-hrr/SKILL.md
  scripts/concepts.py
  core/engineering.md
  core/context.md
  core/compression.md
  core/development.md
  core/research.md
  core/testing.md
  core/review.md
  core/benchmarking.md
  core/versioning.md
  custom/README.md
  custom/project-intent.md
  custom/technical-design.md
  custom/ai-implementation.md
  custom/context-efficiency.md
  custom/delivery.md
  custom/prior-art.md
  custom/patterns.md
  custom/orchestration.md
  custom/model-deliberation.md
  custom/writing.md
  custom/code-comments.md
  custom/evidence-claims.md
  models/routing.yaml
  providers/openai/codex.md
  docs/adoption.md
  docs/concepts-and-signals.md
  docs/references.md
  evals/README.md
  evals/usage-cases.md
  scripts/lookup.rb
  scripts/validate.rb
  scripts/context_ai.py
  scripts/evidence.py
  scripts/check_loadouts.py
  skills/context-loadout/SKILL.md
  schemas/loadout.schema.json
  schemas/lock.schema.json
  schemas/installation.schema.json
  schemas/evidence-bundle-v1.schema.json
  resources.yaml
  capabilities.yaml
  sources.lock.json
  requirements.txt
  .github/workflows/validate.yml
].freeze

def error(message)
  ERRORS << message
end

def relative(path)
  Pathname.new(path).relative_path_from(ROOT).to_s
end

REQUIRED.each do |name|
  path = ROOT.join(name)
  error("missing required file: #{name}") unless path.file?
  error("empty required file: #{name}") if path.file? && path.read.strip.empty?
end

core_files = Dir.glob(ROOT.join("core/*.md")).sort
custom_files = Dir.glob(ROOT.join("custom/*.md")).sort
skill_files = Dir.glob(ROOT.join(".agents/skills/*/SKILL.md")).reject { |path| relative(path).start_with?(".agents/skills/context-") }.sort
overlay_files = Dir.glob(ROOT.join("overlays/*.md")).sort
domain_files = Dir.glob(ROOT.join("domains/**/*.md")).sort
context_files = core_files + custom_files + overlay_files + domain_files
context_files.each do |file|
  words = File.read(file).scan(/\S+/).length
  error("context is too large (#{words} words): #{relative(file)}") if words > 1_200
end

agents = ROOT.join("AGENTS.md")
error("AGENTS.md exceeds the 8 KiB routing budget") if agents.file? && agents.size > 8 * 1024

text_files = Dir.glob(ROOT.join("**/*"), File::FNM_DOTMATCH).select do |path|
  File.file?(path) && !path.include?("/.git/") && !relative(path).start_with?(".agents/skills/context-") && !%w[.context-ai .venv __pycache__ node_modules .examples-output].any? { |dir| Pathname.new(relative(path)).each_filename.include?(dir) }
end

text_files.each do |file|
  content = File.binread(file)
  error("NUL byte in text artifact: #{relative(file)}") if content.include?("\0")
  error("unresolved merge marker in #{relative(file)}") if content.match?(/^(<<<<<<<|>>>>>>>)/)
end

markdown_files = text_files.select { |path| File.extname(path).downcase == ".md" }

skill_files.each do |file|
  frontmatter = File.read(file).match(/\A---\n(.*?)\n---\n/m)
  unless frontmatter
    error("missing skill frontmatter: #{relative(file)}")
    next
  end

  begin
    metadata = YAML.safe_load(frontmatter[1], aliases: false)
    expected_name = Pathname.new(file).dirname.basename.to_s
    error("skill name must match folder: #{relative(file)}") unless metadata.is_a?(Hash) && metadata["name"] == expected_name
    error("skill description is required: #{relative(file)}") unless metadata.is_a?(Hash) && metadata["description"].is_a?(String) && !metadata["description"].strip.empty?
  rescue Psych::Exception => e
    error("invalid skill frontmatter in #{relative(file)}: #{e.message.lines.first.strip}")
  end
end

link_pattern = /!?\[[^\]]*\]\((<[^>]+>|[^\s\)]+)(?:\s+["'][^\)]*["'])?\)/

markdown_files.each do |file|
  content = File.read(file)
  reference_link_pattern = /^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)/
  targets = content.scan(link_pattern).flatten + content.scan(reference_link_pattern).flatten

  targets.uniq.each do |raw_target|
    target = raw_target.sub(/\A</, "").sub(/>\z/, "")
    next if target.empty? || target.start_with?("#")
    next if target.match?(/\A[a-z][a-z0-9+.-]*:/i)

    path_part = target.split("#", 2).first.split("?", 2).first
    next if path_part.empty?

    begin
      path_part = URI::DEFAULT_PARSER.unescape(path_part)
    rescue URI::InvalidURIError
      error("invalid link target in #{relative(file)}: #{target}")
      next
    end

    resolved = if path_part.start_with?("/")
                 Pathname.new(path_part)
               else
                 Pathname.new(file).dirname.join(path_part).cleanpath
               end
    error("broken relative link in #{relative(file)}: #{target}") unless resolved.exist?
  end
end

yaml_files = text_files.select { |path| %w[.yaml .yml].include?(File.extname(path).downcase) }
yaml_documents = {}

def check_duplicate_yaml_keys(node, path)
  if node.is_a?(Psych::Nodes::Mapping)
    seen = []
    node.children.each_slice(2) do |key, value|
      if key.is_a?(Psych::Nodes::Scalar)
        error("duplicate YAML key in #{path}: #{key.value}") if seen.include?(key.value)
        seen << key.value
      end
      check_duplicate_yaml_keys(value, path)
    end
  else
    Array(node.children).each { |child| check_duplicate_yaml_keys(child, path) }
  end
end

yaml_files.each do |file|
  begin
    check_duplicate_yaml_keys(Psych.parse_stream(File.read(file)), relative(file))
    yaml_documents[relative(file)] = YAML.safe_load(
      File.read(file),
      permitted_classes: [],
      permitted_symbols: [],
      aliases: false,
      filename: relative(file)
    )
  rescue Psych::Exception => e
    error("invalid YAML in #{relative(file)}: #{e.message.lines.first.strip}")
  end
end

def valid_review_date?(value)
  return false unless value.is_a?(String) && value.match?(/\A\d{4}-\d{2}-\d{2}\z/)

  Date.iso8601(value)
  true
rescue ArgumentError
  false
end

concept_document = yaml_documents["concepts.yaml"]
concepts = concept_document.is_a?(Hash) ? concept_document["concepts"] : nil
error("concepts.yaml schema_version must be 2") unless concept_document.is_a?(Hash) && concept_document["schema_version"] == 2
error("concepts.yaml concepts must be a non-empty map") unless concepts.is_a?(Hash) && !concepts.empty?
if concepts.is_a?(Hash)
  concepts.each do |id, entry|
    description = entry.is_a?(Hash) ? entry["definition"] : nil
    error("invalid concept id: #{id}") unless id.is_a?(String) && id.match?(/\A[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\z/)
    error("concept #{id} needs a one-line description") unless description.is_a?(String) && !description.strip.empty? && !description.include?("\n")
  end
end

source_document = yaml_documents["sources.yaml"]
sources = source_document.is_a?(Hash) ? source_document["sources"] : nil
error("sources.yaml schema_version must be 1") unless source_document.is_a?(Hash) && source_document["schema_version"] == 1
error("sources.yaml sources must be a non-empty map") unless sources.is_a?(Hash) && !sources.empty?
if sources.is_a?(Hash)
  sources.each do |id, source|
    error("invalid source id: #{id}") unless id.is_a?(String) && id.match?(/\A[a-z][a-z0-9-]*\z/)
    unless source.is_a?(Hash)
      error("source #{id} must be a map")
      next
    end
    %w[title publisher].each do |field|
      error("source #{id} needs #{field}") unless source[field].is_a?(String) && !source[field].strip.empty?
    end
    begin
      url = URI.parse(source["url"].to_s)
      error("source #{id} needs an HTTPS URL") unless url.is_a?(URI::HTTPS) && url.host
    rescue URI::InvalidURIError
      error("source #{id} needs an HTTPS URL")
    end
    error("source #{id} needs a valid YYYY-MM-DD review date") unless valid_review_date?(source["reviewed_on"])
  end
end

signal_ids = []
signal_paths = yaml_documents.keys.grep(%r{\A(?:signals/|providers/[^/]+/signals\.yaml\z)}).sort
error("signals/common.yaml is required") unless signal_paths.include?("signals/common.yaml")
signal_paths.each do |path|
  document = yaml_documents[path]
  unless document.is_a?(Hash) && document["schema_version"] == 1 && document["signals"].is_a?(Hash) && !document["signals"].empty?
    error("#{path} needs schema_version 1 and a non-empty signals map")
    next
  end
  if path == "signals/common.yaml"
    error("#{path} must declare scope: common") unless document["scope"] == "common"
  else
    provider = path.split("/")[1]
    error("#{path} must declare provider: #{provider}") unless document["provider"] == provider
    error("#{path} needs a valid review date") unless valid_review_date?(document["reviewed_on"])
  end
  document["signals"].each do |concept_id, entries|
    error("#{path} uses unknown concept #{concept_id}") unless concepts.is_a?(Hash) && concepts.key?(concept_id)
    unless entries.is_a?(Array) && !entries.empty?
      error("#{path} concept #{concept_id} needs a non-empty signal list")
      next
    end
    entries.each do |signal|
      unless signal.is_a?(Hash)
        error("#{path} concept #{concept_id} has a non-map signal")
        next
      end
      id = signal["id"]
      error("#{path} has an invalid signal id: #{id}") unless id.is_a?(String) && id.match?(/\A[a-z][a-z0-9-]*\z/)
      signal_ids << id if id.is_a?(String)
      error("signal #{id} has an invalid type") unless %w[standard practice native_capability tool].include?(signal["type"])
      %w[name use_when boundary].each do |field|
        error("signal #{id} needs #{field}") unless signal[field].is_a?(String) && !signal[field].strip.empty?
      end
      refs = signal["source_refs"]
      unless refs.is_a?(Array) && !refs.empty? && refs.uniq.length == refs.length
        error("signal #{id} needs unique source_refs")
      end
      Array(refs).each do |ref|
        error("signal #{id} uses unknown source #{ref}") unless sources.is_a?(Hash) && sources.key?(ref)
      end
      if path == "signals/common.yaml"
        error("signal #{id} in common cannot be a native capability") if signal["type"] == "native_capability"
        error("signal #{id} in common must not declare products") if signal.key?("products")
      else
        products = signal["products"]
        unless products.is_a?(Array) && !products.empty? && products.all? { |product| product.is_a?(String) && product.match?(/\A[a-z][a-z0-9-]*\z/) } && products.uniq.length == products.length
          error("signal #{id} needs unique product names")
        end
      end
    end
  end
end
signal_ids.group_by(&:itself).each do |id, ids|
  error("duplicate signal id: #{id}") if ids.length > 1
end

references = ROOT.join("docs/references.md")
reference_text = references.file? ? references.read : ""
accounted_artifacts = (
  core_files +
  custom_files +
  overlay_files +
  domain_files +
  skill_files +
  Dir.glob(ROOT.join("providers/**/*.md")) +
  yaml_files +
  Dir.glob(ROOT.join("evals/**/*")).select { |path| File.file?(path) }
).map { |path| relative(path) }.uniq.sort

accounted_artifacts.each do |name|
  error("docs/references.md does not account for #{name}") unless reference_text.include?(name)
end

sourced_files = text_files.select { |path| Pathname.new(relative(path)).each_filename.include?("sourced") }
sourced_files.each do |file|
  name = relative(file)
  error("docs/references.md lacks provenance for sourced artifact: #{name}") unless reference_text.include?(name)
  if %w[AGENTS.md AGENTS.override.md CLAUDE.md GEMINI.md].include?(File.basename(file))
    error("active instruction filename is not allowed under sourced/: #{name}")
  end
end

routing = yaml_documents["models/routing.yaml"]
if routing.is_a?(Hash)
  error("models/routing.yaml schema_version must be 1") unless routing["schema_version"] == 1
  release = routing["release_version"]
  error("stable publication requires separate future approval") unless release.to_s.start_with?("0.")
  error("models/routing.yaml release_version is not SemVer") unless release.to_s.match?(/\A(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\z/)

  models = routing["models"]
  sources = routing["sources"]
  routes = routing["routes"]
  error("models/routing.yaml models must be a non-empty map") unless models.is_a?(Hash) && !models.empty?
  error("models/routing.yaml sources must be a non-empty map") unless sources.is_a?(Hash) && !sources.empty?
  error("models/routing.yaml routes must be a non-empty list") unless routes.is_a?(Array) && !routes.empty?

  if models.is_a?(Hash) && sources.is_a?(Hash)
    sources.each do |source_ref, source|
      unless source.is_a?(Hash)
        error("source #{source_ref} must be a map")
        next
      end
      error("source #{source_ref} must use an HTTPS URL") unless source["url"].to_s.start_with?("https://")
      error("source #{source_ref} must have a YYYY-MM-DD review date") unless source["reviewed"].to_s.match?(/\A\d{4}-\d{2}-\d{2}\z/)
    end

    models.each do |profile, model|
      unless model.is_a?(Hash)
        error("model profile #{profile} must be a map")
        next
      end
      if model["provider"] == "openai"
        allowed = %w[gpt-6-astra gpt-6.1-sol gpt-6-sol gpt-6-luna]
        error("model profile #{profile} selects unreviewed or retired model: #{model['model']}") unless allowed.include?(model["model"])
        error("model profile #{profile} lifecycle must be current") unless model["lifecycle"] == "current"
      end
      error("model profile #{profile} must name a provider model") if model["provider"].to_s.empty? || model["model"].to_s.empty?
      source_refs = Array(model["source_refs"])
      error("model profile #{profile} must have source_refs") if source_refs.empty?
      source_refs.each do |source_ref|
        error("model profile #{profile} has unknown source_ref #{source_ref}") unless sources.key?(source_ref)
      end
      reasoning = model["reasoning"] || {}
      supported = reasoning["supported"]
      default = reasoning["default"]
      unless supported.is_a?(Array) || supported == "host_defined"
        error("model profile #{profile} must declare supported reasoning levels")
      end
      if supported.is_a?(Array) && !default.nil? && !supported.include?(default)
        error("model profile #{profile} has an unsupported default reasoning level: #{default}")
      end
    end
  end

  if routes.is_a?(Array) && models.is_a?(Hash)
    route_ids = routes.map { |route| route.is_a?(Hash) ? route["id"] : nil }.compact
    duplicates = route_ids.group_by(&:itself).select { |_id, values| values.length > 1 }.keys
    duplicates.each { |id| error("duplicate route id: #{id}") }

    routes.each do |route|
      unless route.is_a?(Hash) && route["id"] && route["match"].is_a?(Hash) && route["select"].is_a?(Hash)
        error("each route must have id, match, and select maps")
        next
      end

      [route["select"], route["fallback"]].compact.each do |selection|
        unless selection.is_a?(Hash)
          error("route #{route['id']} selection must be a map")
          next
        end
        profile = selection["model_profile"]
        unless models.key?(profile)
          error("route #{route['id']} selects unknown model profile: #{profile}")
          next
        end
        supported = models.fetch(profile).fetch("reasoning", {})["supported"]
        effort = selection["reasoning"]
        if supported.is_a?(Array) && !effort.nil? && !supported.include?(effort)
          error("route #{route['id']} selects unsupported #{profile} reasoning: #{effort}")
        end
      end
    end

    fallback = routing.dig("matching", "fallback_route")
    error("fallback route does not exist: #{fallback}") unless route_ids.include?(fallback)
    error("fallback route must be listed last") unless route_ids.last == fallback
    fallback_match = routes.find { |route| route.is_a?(Hash) && route["id"] == fallback }
    unless fallback_match && fallback_match["match"] == { "intent" => "*" }
      error("fallback route must be an intent wildcard")
    end

    Array(routing["recommended_workflow"]).each do |stage|
      next unless stage.is_a?(Hash)
      error("recommended workflow references unknown route: #{stage['route']}") unless route_ids.include?(stage["route"])
    end
  end
else
  error("models/routing.yaml must contain a map") if yaml_documents.key?("models/routing.yaml")
end

if ERRORS.empty?
  puts "Validation passed: #{REQUIRED.length} required files, #{markdown_files.length} Markdown files, #{yaml_files.length} YAML file(s)."
else
  warn "Validation failed with #{ERRORS.length} error(s):"
  ERRORS.each { |message| warn "- #{message}" }
  exit 1
end
