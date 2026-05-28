import type { BackendVulnerabilityCategory } from './recommendation';

export type SmokingStatus = 'never' | 'former' | 'current';
export type ActivityLevel = 'sedentary' | 'moderate' | 'active';
export type PollutionSensitivity = 'low' | 'medium' | 'high';

export type PreferredLocation = {
  name: string;
  latitude: number;
  longitude: number;
};

export type UserProfile = {
  age: number;
  gender?: string;
  chronic_diseases: string[];
  asthma: boolean;
  cardiovascular: boolean;
  allergies: string[];
  smoking_status: SmokingStatus;
  activity_level: ActivityLevel;
  pollution_sensitivity: PollutionSensitivity;
  preferred_locations: PreferredLocation[];
  is_pregnant?: boolean;
  outdoor_worker?: boolean;
  intense_sport?: boolean;
  low_socioeconomic?: boolean;
};

export type UserOnboardingRequest = UserProfile & {
  user_id: string;
  email?: string;
};

export type UserOnboardingResponse = {
  user_id: string;
  vulnerability_category: BackendVulnerabilityCategory;
  vulnerability_score: number;
  contributing_factors: string[];
  profile_last_updated: string;
};

export type User = {
  user_id: string;
  name?: string;
  email?: string;
  vulnerability_category: BackendVulnerabilityCategory;
  vulnerability_score?: number;
  contributing_factors?: string[];
  profile_last_updated?: string;
  profile: UserProfile;
};

export type AuthUser = {
  user_id: string;
  email: string;
  name?: string;
  onboarding_completed: boolean;
};

export type AuthResponse = {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
};
