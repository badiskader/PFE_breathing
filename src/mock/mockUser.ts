import type { AuthResponse, User, UserOnboardingRequest, UserOnboardingResponse } from '@/types';

export const mockUserId = 'user_ahmed_demo';

export const mockOnboardingRequest = {
  user_id: mockUserId,
  email: 'ahmed.mansouri@email.com',
  age: 34,
  gender: 'male',
  chronic_diseases: ['asthma', 'rhinitis'],
  asthma: true,
  cardiovascular: false,
  allergies: ['pollen', 'dust_mites'],
  smoking_status: 'never',
  activity_level: 'moderate',
  pollution_sensitivity: 'high',
  preferred_locations: [
    {
      name: 'Home',
      latitude: 36.74,
      longitude: 3.06,
    },
    {
      name: 'Work',
      latitude: 36.75,
      longitude: 3.06,
    },
  ],
  is_pregnant: false,
  outdoor_worker: false,
  intense_sport: true,
  low_socioeconomic: false,
} satisfies UserOnboardingRequest;

export const mockOnboardingResponse = {
  user_id: mockUserId,
  vulnerability_category: 'sensible',
  vulnerability_score: 0.62,
  contributing_factors: ['asthma', 'high_sensitivity', 'intense_sport'],
  profile_last_updated: '2026-05-21T18:55:00Z',
} satisfies UserOnboardingResponse;

export const mockUser = {
  user_id: mockUserId,
  name: 'Ahmed Mansouri',
  email: mockOnboardingRequest.email,
  vulnerability_category: mockOnboardingResponse.vulnerability_category,
  vulnerability_score: mockOnboardingResponse.vulnerability_score,
  contributing_factors: mockOnboardingResponse.contributing_factors,
  profile_last_updated: mockOnboardingResponse.profile_last_updated,
  profile: {
    age: mockOnboardingRequest.age,
    gender: mockOnboardingRequest.gender,
    chronic_diseases: mockOnboardingRequest.chronic_diseases,
    asthma: mockOnboardingRequest.asthma,
    cardiovascular: mockOnboardingRequest.cardiovascular,
    allergies: mockOnboardingRequest.allergies,
    smoking_status: mockOnboardingRequest.smoking_status,
    activity_level: mockOnboardingRequest.activity_level,
    pollution_sensitivity: mockOnboardingRequest.pollution_sensitivity,
    preferred_locations: mockOnboardingRequest.preferred_locations,
    is_pregnant: mockOnboardingRequest.is_pregnant,
    outdoor_worker: mockOnboardingRequest.outdoor_worker,
    intense_sport: mockOnboardingRequest.intense_sport,
    low_socioeconomic: mockOnboardingRequest.low_socioeconomic,
  },
} satisfies User;

export const mockAuthResponse = {
  access_token: 'mock-jwt-token',
  token_type: 'bearer',
  user: {
    user_id: mockUser.user_id,
    email: mockUser.email,
    name: mockUser.name,
    onboarding_completed: true,
  },
} satisfies AuthResponse;
