# Executes the actual Fastlane DSL at its external shell/store boundary.
# No Fastlane gem, signing material, network or store credentials are used.
require 'tmpdir'
require 'fileutils'
require 'shellwords'
require 'ostruct'

ROOT = File.expand_path('..', __dir__)
CONFIG = {'API_BASE_URL'=>'https://api.example.test', 'COGNITO_DOMAIN'=>'glean.auth.eu-west-2.amazoncognito.com', 'COGNITO_CLIENT_ID'=>'abc123'}
# Never let the lane DSL read operator credential environment in this probe.
%w[ASC_KEY_ID ASC_ISSUER_ID ASC_KEY_CONTENT PLAY_STORE_JSON_KEY].each { |key| ENV[key] = 'fixture-only' }
module UI
  def self.user_error!(message); raise message; end
  def self.message(_); end
end
module Supply
  def self.config; {package_name: 'com.ruaridhw.glean'}; end
  class Client
    def self.make_from_config; new; end
    def begin_edit(package_name:); end
    def abort_current_edit; end
    def tracks
      [OpenStruct.new(track: 'internal', releases: [OpenStruct.new(version_codes: ['9'])]), OpenStruct.new(track: 'production', releases: [OpenStruct.new(version_codes: ['42'])]), OpenStruct.new(track: 'custom-preview', releases: [OpenStruct.new(version_codes: ['101'])])]
    end
  end
end

def default_platform(_); end
def platform(name); @platform = name; yield; end
def desc(_); end
def lane(name, &block); (@lanes ||= {})[[@platform, name]] = block; end
def sh(command); (@commands ||= []) << command; end
def google_play_track_version_codes(**_); [9]; end
def app_store_connect_api_key(**_); @store_calls = (@store_calls || 0)+1; {}; end
def app_store_build_number(**_); 9; end
def upload_to_play_store(**_); end
def upload_to_testflight(**_); end

load File.join(ROOT, 'android/fastlane/Fastfile')
load File.join(ROOT, 'ios/fastlane/Fastfile')
failures = []
cases = 0
Dir.mktmpdir do |dir|
  %w[android/fastlane ios/fastlane build/ios/ipa].each { |p| FileUtils.mkdir_p(File.join(dir,p)) }
  File.write(File.join(dir,'android/key.properties'), 'fixture only')
  File.write(File.join(dir,'pubspec.yaml'), 'version: 0.1.0+1')
  File.write(File.join(dir,'build/ios/ipa/test.ipa'), '')
  [[:android,:internal],[:ios,:beta]].each do |target|
    CONFIG.each { |k,v| ENV[k]=v }
    @commands=[]
    cases+=1
    begin
      Dir.chdir(File.join(dir,target.first.to_s,'fastlane')) { @lanes[target].call }
      command = @commands.find { |c| c.include?('flutter build') }
      args = Shellwords.split(command || '')
      CONFIG.each { |key,value| raise "#{key} missing from release #{target}" unless args.include?("--dart-define=#{key}=#{value}") }
      raise 'wrong production entrypoint' unless args.include?('lib/main.dart') && !args.any? { |a| a.include?('main_e2e') }
      raise 'wrong release mode' unless args.include?('--release')
      if target.first==:android
        raise 'custom/highest Play track not considered' unless args.include?('--build-number=102')
      end
    rescue => e; failures << e.message; end
    CONFIG.keys.each do |missing|
      cases+=1
      CONFIG.each { |k,v| ENV[k]=v }; ENV.delete(missing); @commands=[]; @store_calls=0
      begin
        begin
          Dir.chdir(File.join(dir,target.first.to_s,'fastlane')) { @lanes[target].call }
          raise 'release accepted missing configuration'
        rescue => e
          raise e unless e.message.include?(missing)
        end
        raise 'configuration was checked after build/store access' unless @commands.empty? && @store_calls==0
      rescue => e; failures << "#{target}/#{missing}: #{e.message}"; end
    end
  end
end
puts "Release lane behavior: #{cases-failures.length}/#{cases} passed"
failures.each { |f| puts "FAIL: #{f}" }
exit(failures.empty? ? 0 : 1)
