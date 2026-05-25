/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEV_AUTH?: string;
  readonly VITE_DEV_EMAIL?: string;
  readonly VITE_DEV_ROLES?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
