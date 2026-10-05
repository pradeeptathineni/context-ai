#!/usr/bin/env ruby
# frozen_string_literal: true

require "pathname"
require "yaml"

ROOT = Pathname.new(__dir__).parent

def load_yaml(path)
  YAML.safe_load(File.read(ROOT.join(path)), aliases: false)
end

def usage(status = 2)
  stream = status.zero? ? $stdout : $stderr
  stream.puts "Usage: ruby scripts/lookup.rb --search WORDS"
  stream.puts "       ruby scripts/lookup.rb CONCEPT_ID [--provider NAME [--product NAME]]"
  exit status
end

usage(0) if ARGV == ["--help"]

concepts = load_yaml("concepts.yaml").fetch("concepts")

if ARGV.first == "--search"
  query = ARGV.drop(1).join(" ").strip.downcase
  usage if query.empty?
  matches = concepts.select { |id, description| "#{id} #{description}".downcase.include?(query) }
  matches.each { |id, description| puts "#{id}: #{description}" }
  exit(matches.empty? ? 1 : 0)
end

id = ARGV.shift
usage unless id
abort "Unknown concept ID: #{id}. Try --search WORDS." unless concepts.key?(id)

provider = nil
product = nil
until ARGV.empty?
  option = ARGV.shift
  value = ARGV.shift
  usage unless value && value.match?(/\A[a-z][a-z0-9-]*\z/)
  case option
  when "--provider"
    usage if provider
    provider = value
  when "--product"
    usage if product
    product = value
  else
    usage
  end
end
usage if product && !provider

signal_files = ["signals/common.yaml"]
if provider
  path = "providers/#{provider}/signals.yaml"
  abort "Unknown provider: #{provider}" unless ROOT.join(path).file?
  signal_files << path
end

sources = load_yaml("sources.yaml").fetch("sources")
puts "#{id}: #{concepts.fetch(id)}"
found = false
signal_files.each do |path|
  document = load_yaml(path)
  entries = document.fetch("signals").fetch(id, [])
  entries = entries.select { |signal| signal.fetch("products").include?(product) } if product && provider && path != "signals/common.yaml"
  next if entries.empty?

  found = true
  puts "\n#{path}:"
  entries.each do |signal|
    scope = signal["products"] ? " (#{signal.fetch('products').join(', ')})" : ""
    puts "- #{signal.fetch('name')} [#{signal.fetch('type')}]#{scope}"
    puts "  Use when: #{signal.fetch('use_when')}"
    puts "  Boundary: #{signal.fetch('boundary')}"
    signal.fetch("source_refs").each do |ref|
      source = sources.fetch(ref)
      puts "  Source: #{source.fetch('publisher')}, #{source.fetch('title')} — #{source.fetch('url')} (reviewed #{source.fetch('reviewed_on')})"
    end
  end
end
puts "\nNo indexed signals for this concept and scope." unless found
