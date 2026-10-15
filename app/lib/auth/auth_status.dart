/// Coarse auth state the router gates navigation on.
///
/// `expired` is deliberately distinct from `signedOut`: a token expiry must
/// not evict the user from their (fully local) data — it only gates
/// AI-backed features behind the signed-out banner, a feature-level concern.
/// The router's redirect therefore only fires for `signedOut`.
enum AuthStatus { signedOut, active, expired }
