export const supportedLanguages = ['en', 'fr'] as const;

export type AppLanguage = (typeof supportedLanguages)[number];

export function normalizeLanguage(languageCode?: string | null): AppLanguage {
  if (languageCode?.toLowerCase().startsWith('fr')) {
    return 'fr';
  }

  return 'en';
}
