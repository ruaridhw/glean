require 'uri'
require 'shellwords'

# These are public deployment identifiers, not secrets. Validate before any
# signing/store action, then pass Dart's compile-time values to both builders.
def release_defines
  values = %w[API_BASE_URL COGNITO_DOMAIN COGNITO_CLIENT_ID].to_h do |name|
    value = ENV[name].to_s.strip
    UI.user_error!("#{name} is required for a configured production build") if value.empty?
    [name, value]
  end
  api = URI.parse(values['API_BASE_URL']) rescue nil
  unless api && api.scheme == 'https' && api.host && !api.userinfo && !%w[localhost 127.0.0.1 ::1].include?(api.host)
    UI.user_error!('API_BASE_URL must be a production HTTPS URL without embedded credentials')
  end
  unless values['COGNITO_DOMAIN'].match?(/\A[a-zA-Z0-9.-]+\.[a-zA-Z0-9-]+\z/)
    UI.user_error!('COGNITO_DOMAIN must be a hostname, without scheme or path')
  end
  unless values['COGNITO_CLIENT_ID'].match?(/\A[a-zA-Z0-9]+\z/)
    UI.user_error!('COGNITO_CLIENT_ID must be a Cognito app client identifier')
  end
  values.map { |name,value| Shellwords.escape("--dart-define=#{name}=#{value}") }.join(' ')
end
