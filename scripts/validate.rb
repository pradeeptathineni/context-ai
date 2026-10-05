#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"
require "uri"
require "yaml"

ROOT = Pathname.new(__dir__).parent.expand_path
ERRORS = []

REQUIRED = %w[
  AGENTS.md
  README.md
  CHANGELOG.md
  LICENSE
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
  docs/references.md
  evals/README.md
  evals/usage-cases.md
  scripts/validate.rb
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
context_files = core_files + custom_files
context_files.each do |file|
  words = File.read(file).scan(/\S+/).length
  error("context is too large (#{words} words): #{relative(file)}") if words > 1_200
end

agents = ROOT.join("AGENTS.md")
error("AGENTS.md exceeds the 8 KiB routing budget") if agents.file? && agents.size > 8 * 1024

text_files = Dir.glob(ROOT.join("**/*"), File::FNM_DOTMATCH).select do |path|
  File.file?(path) && !path.include?("/.git/")
end

text_files.each do |file|
  content = File.binread(file)
  error("NUL byte in text artifact: #{relative(file)}") if content.include?("\0")
  error("unresolved merge marker in #{relative(file)}") if content.match?(/^(<<<<<<<|>>>>>>>)/)
end

markdown_files = text_files.select { |path| File.extname(path).downcase == ".md" }
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
yaml_files.each do |file|
  begin
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

references = ROOT.join("docs/references.md")
reference_text = references.file? ? references.read : ""
accounted_artifacts = (
  core_files +
  custom_files +
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
