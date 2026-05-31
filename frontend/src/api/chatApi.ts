import type { ChatHistoryResponse, ChatRequest, ChatResponse } from '@/types';

import { apiRequest } from './client';

export function sendChatMessage(request: ChatRequest) {
  return apiRequest<ChatResponse>('/chat', {
    body: JSON.stringify(request),
    method: 'POST',
  });
}

export function getChatHistory(sessionId: string) {
  return apiRequest<ChatHistoryResponse>(`/chat/${encodeURIComponent(sessionId)}/history`);
}
