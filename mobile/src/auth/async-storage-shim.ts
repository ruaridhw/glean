// Shim for @react-native-async-storage/async-storage
// Used by amazon-cognito-identity-js at runtime.
// In local dev we bypass auth, so this is a no-op store.

const store = new Map<string, string>();

export default {
  getItem: async (key: string) => store.get(key) ?? null,
  setItem: async (key: string, value: string) => {
    store.set(key, value);
  },
  removeItem: async (key: string) => {
    store.delete(key);
  },
  mergeItem: async (key: string, value: string) => {
    store.set(key, value);
  },
  clear: async () => {
    store.clear();
  },
  getAllKeys: async () => [...store.keys()],
  multiGet: async (keys: string[]) =>
    keys.map((k) => [k, store.get(k) ?? null] as [string, string | null]),
  multiSet: async (pairs: [string, string][]) => {
    for (const [k, v] of pairs) store.set(k, v);
  },
  multiRemove: async (keys: string[]) => {
    for (const k of keys) store.delete(k);
  },
  multiMerge: async (pairs: [string, string][]) => {
    for (const [k, v] of pairs) store.set(k, v);
  },
};
