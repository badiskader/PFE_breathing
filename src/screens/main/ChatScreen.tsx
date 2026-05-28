import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useMemo, useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { sendChatMessage } from '@/api';
import { mockChatMessages, mockChatResponse, mockSessionId, mockSuggestedPrompts, mockUserId } from '@/mock';
import { colors, shadows } from '@/theme';
import type { AgentUsed, ChatMessage } from '@/types';

export function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>(mockChatMessages);
  const [input, setInput] = useState('');
  const [sessionId, setSessionId] = useState(mockSessionId);
  const [isSending, setIsSending] = useState(false);
  const scrollViewRef = useRef<ScrollView>(null);
  const suggestions = useMemo(() => mockSuggestedPrompts, []);

  async function handleSend() {
    const trimmedInput = input.trim();

    if (!trimmedInput || isSending) {
      return;
    }

    const userMessage: ChatMessage = {
      content: trimmedInput,
      id: `local_user_${Date.now()}`,
      role: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages((currentMessages) => [...currentMessages, userMessage]);
    setInput('');
    setIsSending(true);

    try {
      const response = await sendChatMessage({
        message: trimmedInput,
        session_id: sessionId,
        user_id: mockUserId,
      });

      setSessionId(response.session_id);
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          agent_used: response.agent_used,
          content: response.response,
          id: `local_assistant_${Date.now()}`,
          role: 'assistant',
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch {
      setMessages((currentMessages) => [
        ...currentMessages,
        {
          agent_used: mockChatResponse.agent_used,
          content: mockChatResponse.response,
          id: `local_assistant_${Date.now()}`,
          role: 'assistant',
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleNewChat() {
    setMessages([]);
    setInput('');
    setSessionId(mockSessionId);
  }

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <KeyboardAvoidingView
        behavior={Platform.select({ ios: 'padding', default: undefined })}
        style={styles.container}
      >
        <View style={styles.header}>
          <View style={styles.headerIdentity}>
            <LinearGradient
              colors={[colors.primaryBlue, colors.secondaryCyan]}
              end={{ x: 1, y: 1 }}
              start={{ x: 0, y: 0 }}
              style={styles.logo}
            >
              <Text style={styles.logoText}>AQ</Text>
            </LinearGradient>
            <View>
              <Text style={styles.headerTitle}>AI Health Advisor</Text>
              <View style={styles.statusRow}>
                <View style={styles.onlineDot} />
                <Text style={styles.statusText}>Online · Multi-agent</Text>
              </View>
            </View>
          </View>

          <View style={styles.headerActions}>
            <View style={styles.bellWrap}>
              <Ionicons color={colors.textSecondary} name="notifications-outline" size={26} />
              <View style={styles.notificationDot} />
            </View>
            <Pressable accessibilityRole="button" onPress={handleNewChat} style={styles.newChatButton}>
              <Text style={styles.newChatText}>+ New chat</Text>
            </Pressable>
          </View>
        </View>

        <ScrollView
          ref={scrollViewRef}
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.messageContent}
          onContentSizeChange={() => {
            if (isSending) {
              scrollViewRef.current?.scrollToEnd({ animated: true });
            }
          }}
        >
          {messages.map((message) => (
            <ChatMessageBubble key={message.id} message={message} />
          ))}
          <AssistantTyping />
        </ScrollView>

        <View style={styles.bottomPanel}>
          <Text style={styles.suggestionsTitle}>Suggestions</Text>
          <View style={styles.suggestionList}>
            {suggestions.map((suggestion) => (
              <Pressable key={suggestion} onPress={() => setInput(suggestion)} style={styles.suggestionChip}>
                <Text style={styles.suggestionText}>{suggestion}</Text>
              </Pressable>
            ))}
          </View>

          <View style={styles.composerRow}>
            <View style={styles.inputWrap}>
              <TextInput
                multiline
                onChangeText={setInput}
                placeholder="Posez votre question..."
                placeholderTextColor={colors.textMuted}
                style={styles.input}
                value={input}
              />
              <Ionicons color={colors.textMuted} name="mic-outline" size={24} />
            </View>
            <Pressable accessibilityRole="button" onPress={handleSend} style={styles.sendButton}>
              <Ionicons color={colors.white} name="send-outline" size={24} />
            </Pressable>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ChatMessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <View style={styles.userMessageBlock}>
        <LinearGradient
          colors={[colors.primaryBlue, colors.secondaryCyan]}
          end={{ x: 1, y: 0 }}
          start={{ x: 0, y: 1 }}
          style={styles.userBubble}
        >
          <Text style={styles.userMessageText}>{message.content}</Text>
        </LinearGradient>
        <Text style={styles.userTime}>{formatChatTime(message.timestamp)}</Text>
      </View>
    );
  }

  return (
    <View style={styles.assistantBlock}>
      <AssistantLabel />
      <View style={styles.assistantBubble}>
        <Text style={styles.assistantMessageText}>{message.content}</Text>
      </View>
      {message.agent_used ? (
        <View style={styles.agentMetaRow}>
          <View style={[styles.agentTag, agentTagStyle(message.agent_used)]}>
            <Text style={styles.agentTagText}>{message.agent_used}</Text>
          </View>
          <Text style={styles.agentTime}>{formatChatTime(message.timestamp)}</Text>
        </View>
      ) : null}
    </View>
  );
}

function AssistantLabel() {
  return (
    <View style={styles.assistantLabelRow}>
      <View style={styles.aiDot}>
        <Text style={styles.aiDotText}>AI</Text>
      </View>
      <Text style={styles.assistantName}>AirPulse AI</Text>
    </View>
  );
}

function AssistantTyping() {
  return (
    <View style={styles.assistantBlock}>
      <AssistantLabel />
      <View style={styles.typingBubble}>
        <View style={styles.typingDot} />
        <View style={styles.typingDot} />
        <View style={styles.typingDot} />
      </View>
    </View>
  );
}

function formatChatTime(timestamp: string) {
  return new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    hour12: false,
    minute: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(timestamp));
}

function agentTagStyle(agent: AgentUsed) {
  if (agent === 'Analytics') {
    return styles.analyticsTag;
  }

  if (agent === 'Forecast & Reco') {
    return styles.forecastTag;
  }

  return styles.healthTag;
}

const styles = StyleSheet.create({
  agentMetaRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 7,
    marginTop: 5,
  },
  agentTag: {
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  agentTagText: {
    color: '#111827',
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 17,
  },
  agentTime: {
    color: colors.textMuted,
    fontSize: 13,
  },
  aiDot: {
    alignItems: 'center',
    backgroundColor: '#2B9CF0',
    borderRadius: 11,
    height: 22,
    justifyContent: 'center',
    width: 22,
  },
  aiDotText: {
    color: colors.white,
    fontSize: 10,
    fontWeight: '800',
  },
  analyticsTag: {
    backgroundColor: '#C8F7DD',
  },
  assistantBlock: {
    alignSelf: 'flex-start',
    marginTop: 12,
    maxWidth: '76%',
  },
  assistantBubble: {
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 16,
    borderTopLeftRadius: 6,
    borderWidth: StyleSheet.hairlineWidth,
    marginTop: 7,
    paddingHorizontal: 14,
    paddingVertical: 12,
    ...shadows.card,
  },
  assistantLabelRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 9,
  },
  assistantMessageText: {
    color: '#3E4A5E',
    fontSize: 18,
    lineHeight: 27,
  },
  assistantName: {
    color: colors.textMuted,
    fontSize: 14,
    lineHeight: 19,
  },
  bellWrap: {
    position: 'relative',
  },
  bottomPanel: {
    backgroundColor: colors.white,
    borderTopColor: colors.border,
    borderTopWidth: StyleSheet.hairlineWidth,
    paddingHorizontal: 16,
    paddingTop: 11,
  },
  composerRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 12,
    paddingBottom: 10,
    paddingTop: 10,
  },
  container: {
    backgroundColor: '#F6F7F9',
    flex: 1,
  },
  forecastTag: {
    backgroundColor: '#FFF2B8',
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.white,
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: 15,
    paddingHorizontal: 16,
    paddingTop: 14,
  },
  headerActions: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 15,
  },
  headerIdentity: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 11,
  },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 21,
  },
  healthTag: {
    backgroundColor: '#FFE1EF',
  },
  input: {
    color: colors.textPrimary,
    flex: 1,
    fontSize: 16,
    lineHeight: 21,
    maxHeight: 72,
    minHeight: 24,
    padding: 0,
  },
  inputWrap: {
    alignItems: 'center',
    backgroundColor: '#F0F2F5',
    borderRadius: 20,
    flex: 1,
    flexDirection: 'row',
    gap: 10,
    minHeight: 40,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  logo: {
    alignItems: 'center',
    borderRadius: 13,
    height: 36,
    justifyContent: 'center',
    width: 36,
  },
  logoText: {
    color: colors.white,
    fontSize: 15,
    fontWeight: '900',
  },
  messageContent: {
    paddingBottom: 12,
    paddingHorizontal: 16,
    paddingTop: 15,
  },
  newChatButton: {
    alignItems: 'center',
    backgroundColor: '#EEF5FF',
    borderRadius: 12,
    height: 32,
    justifyContent: 'center',
    paddingHorizontal: 13,
  },
  newChatText: {
    color: '#0057FF',
    fontSize: 14,
    fontWeight: '700',
  },
  notificationDot: {
    backgroundColor: '#FF3345',
    borderColor: colors.white,
    borderRadius: 6,
    borderWidth: 2,
    height: 12,
    position: 'absolute',
    right: -1,
    top: -1,
    width: 12,
  },
  onlineDot: {
    backgroundColor: '#23C36B',
    borderRadius: 4,
    height: 8,
    width: 8,
  },
  safeArea: {
    backgroundColor: colors.white,
    flex: 1,
  },
  sendButton: {
    alignItems: 'center',
    backgroundColor: '#17AEE0',
    borderRadius: 22,
    height: 44,
    justifyContent: 'center',
    width: 44,
  },
  statusRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 5,
    marginTop: 2,
  },
  statusText: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 17,
  },
  suggestionChip: {
    alignSelf: 'flex-start',
    backgroundColor: colors.white,
    borderColor: '#DADFE7',
    borderRadius: 15,
    borderWidth: 1,
    paddingHorizontal: 11,
    paddingVertical: 5,
  },
  suggestionList: {
    gap: 6,
    marginTop: 7,
  },
  suggestionText: {
    color: '#4B5567',
    fontSize: 13,
    fontWeight: '600',
    lineHeight: 17,
  },
  suggestionsTitle: {
    color: colors.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  typingBubble: {
    alignItems: 'center',
    alignSelf: 'flex-start',
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 4,
    flexDirection: 'row',
    gap: 7,
    marginLeft: 32,
    marginTop: 6,
    paddingHorizontal: 18,
    paddingVertical: 11,
    ...shadows.card,
  },
  typingDot: {
    backgroundColor: colors.textMuted,
    borderRadius: 3,
    height: 6,
    width: 6,
  },
  userBubble: {
    borderRadius: 17,
    borderTopRightRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  userMessageBlock: {
    alignSelf: 'flex-end',
    marginLeft: 64,
    marginTop: 4,
    maxWidth: '76%',
  },
  userMessageText: {
    color: colors.white,
    fontSize: 18,
    lineHeight: 27,
  },
  userTime: {
    alignSelf: 'flex-end',
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 5,
  },
});
