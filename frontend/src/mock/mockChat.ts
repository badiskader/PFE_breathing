import type { ChatHistoryResponse, ChatResponse, ChatSession } from '@/types';

import { mockUserId } from './mockUser';

export const mockSessionId = 'session_airpulse_demo';

export const mockChatMessages = [
  {
    id: 'msg_001',
    role: 'user',
    content: "Quel est le niveau de qualité de l'air à Alger ce soir?",
    timestamp: '2026-05-21T18:52:00Z',
  },
  {
    id: 'msg_002',
    role: 'assistant',
    content:
      "Ce soir à Alger, l'indice AQI est de 22 — Bon. Les niveaux de PM2.5 sont à 4.0 µg/m³, bien en dessous du seuil de l'OMS. C'est une excellente soirée pour les activités en plein air.",
    timestamp: '2026-05-21T18:52:12Z',
    agent_used: 'Analytics',
  },
  {
    id: 'msg_003',
    role: 'user',
    content: 'Est-ce que je peux aller courir demain matin?',
    timestamp: '2026-05-21T18:54:00Z',
  },
  {
    id: 'msg_004',
    role: 'assistant',
    content:
      "Demain matin, la qualité de l'air devrait rester dans la catégorie Modérée (AQI ~65–80) entre 6h et 9h en raison de l'accumulation nocturne de PM2.5. Pour une course, je recommande de courir avant 7h ou d'attendre 10h quand les vents disperseront les polluants. Portez un masque N95 si vous êtes sensible aux particules.",
    timestamp: '2026-05-21T18:55:00Z',
    agent_used: 'Forecast & Reco',
  },
  {
    id: 'msg_005',
    role: 'user',
    content: "Comment l'ozone affecte-t-il mon asthme?",
    timestamp: '2026-05-21T18:58:00Z',
  },
  {
    id: 'msg_006',
    role: 'assistant',
    content:
      "L'ozone (O3) est un irritant respiratoire puissant. Pour les asthmatiques, une exposition à des niveaux d'O3 > 70 ppb peut déclencher des crises, causer une inflammation des voies aériennes et réduire la capacité pulmonaire. Actuellement l'O3 à Alger est à 31 µg/m³ — niveau sûr. Consultez votre médecin pour adapter votre plan d'action en cas de montée des niveaux.",
    timestamp: '2026-05-21T18:59:00Z',
    agent_used: 'Health context',
  },
] satisfies ChatSession['messages'];

export const mockChatSession = {
  session_id: mockSessionId,
  user_id: mockUserId,
  messages: mockChatMessages,
} satisfies ChatSession;

export const mockChatHistoryResponse = {
  session_id: mockSessionId,
  user_id: mockUserId,
  created_at: '2026-05-21T18:52:00Z',
  updated_at: '2026-05-21T18:59:00Z',
  message_count: mockChatMessages.length,
  messages: mockChatMessages.map(({ id: _id, ...message }) => message),
} satisfies ChatHistoryResponse;

export const mockChatResponse = {
  session_id: mockSessionId,
  agent_used: 'Forecast & Reco',
  response:
    "Pour une sortie demain matin, privilégiez le début de matinée et évitez les efforts intenses si les PM2.5 augmentent.",
} satisfies ChatResponse;

export const mockSuggestedPrompts = [
  "Qu'est-ce que le PM2.5 ?",
  'Quel est le pire capteur actuellement ?',
  'Est-ce que je peux courir demain matin ?',
  "Comment l'ozone affecte-t-il mon asthme ?",
];
