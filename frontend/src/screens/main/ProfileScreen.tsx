import { Ionicons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { LinearGradient } from 'expo-linear-gradient';
import type { ComponentProps, ReactNode } from 'react';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { mockUser } from '@/mock';
import type { MainStackParamList } from '@/navigation/types';
import { colors, shadows } from '@/theme';

type MaterialIconName = ComponentProps<typeof MaterialCommunityIcons>['name'];

export function ProfileScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<MainStackParamList>>();
  const [pushEnabled, setPushEnabled] = useState(true);
  const [briefingEnabled, setBriefingEnabled] = useState(true);
  const [language, setLanguage] = useState<'FR' | 'EN'>('FR');
  const [theme, setTheme] = useState<'System' | 'Light' | 'Dark'>('System');
  const profile = mockUser.profile;

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        <View style={styles.header}>
          <View style={styles.headerBrand}>
            <LinearGradient
              colors={[colors.primaryBlue, colors.secondaryCyan]}
              end={{ x: 1, y: 1 }}
              start={{ x: 0, y: 0 }}
              style={styles.logo}
            >
              <Text style={styles.logoText}>AQ</Text>
            </LinearGradient>
            <Text style={styles.headerTitle}>Profile</Text>
          </View>
          <View style={styles.bellWrap}>
            <Ionicons color={colors.textSecondary} name="notifications-outline" size={29} />
            <View style={styles.notificationDot} />
          </View>
        </View>

        <View style={styles.profileHero}>
          <LinearGradient
            colors={['#5275FF', colors.purpleAccent]}
            end={{ x: 1, y: 1 }}
            start={{ x: 0, y: 0 }}
            style={styles.avatar}
          >
            <Text style={styles.avatarText}>AM</Text>
          </LinearGradient>
          <Text style={styles.name}>{mockUser.name}</Text>
          <Text style={styles.email}>{mockUser.email}</Text>
          <View style={styles.sensitivityPill}>
            <Text style={styles.sensitivityText}>⚠ Sensible</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => navigation.navigate('EditProfile')}
            style={styles.editButtonWrap}
          >
            <LinearGradient
              colors={[colors.primaryBlue, colors.secondaryCyan]}
              end={{ x: 1, y: 0 }}
              start={{ x: 0, y: 0 }}
              style={styles.editButton}
            >
              <Text style={styles.editButtonText}>Edit profile</Text>
            </LinearGradient>
          </Pressable>
        </View>

        <View style={styles.cardsPane}>
          <ProfileCard icon="hospital-building" title="Health profile">
            <InfoRow label="Age" value={`${profile.age} ans`} />
            <InfoRow label="Gender" value="Masculin" />
            <InfoRow
              label="Chronic diseases"
              value={
                <View style={styles.chipsRow}>
                  <Chip label="Asthme" tone="orange" />
                  <Chip label="Rhinite" tone="blue" />
                </View>
              }
            />
            <InfoRow label="Cardiovascular" value="Non" />
            <InfoRow
              label="Allergies"
              value={
                <View style={styles.chipsRow}>
                  <Chip label="Pollen" tone="green" />
                  <Chip label="Acariens" tone="green" />
                </View>
              }
            />
            <InfoRow label="Smoking" value="Non-fumeur" last />
          </ProfileCard>

          <ProfileCard icon="run-fast" title="Lifestyle">
            <InfoRow label="Activity level" value={activityLabel(profile.activity_level)} />
            <InfoRow label="Pollution sensitivity" value={sensitivityLabel(profile.pollution_sensitivity)} />
            <InfoRow label="Outdoor worker" value={profile.outdoor_worker ? 'Oui' : 'Non'} />
            <InfoRow label="Intense sport" value={profile.intense_sport ? 'Oui' : 'Non'} />
            <InfoRow label="Pregnant" value={profile.is_pregnant ? 'Oui' : 'N/A'} last />
          </ProfileCard>

          <ProfileCard icon="map-marker-radius-outline" title="Preferred locations">
            <View style={styles.locationsList}>
              {profile.preferred_locations.map((location) => (
                <View key={location.name} style={styles.locationRow}>
                  <View style={styles.locationIconWrap}>
                    <MaterialCommunityIcons color="#172033" name="map" size={18} />
                  </View>
                  <Text style={styles.locationText}>
                    {location.latitude.toFixed(2)}° N, {location.longitude.toFixed(2)}° E
                  </Text>
                </View>
              ))}
              <Pressable accessibilityRole="button" style={styles.addLocationButton}>
                <Text style={styles.addLocationText}>+ Add location</Text>
              </Pressable>
            </View>
          </ProfileCard>

          <ProfileCard icon="bell-outline" title="Notifications">
            <View style={styles.settingRow}>
              <Text style={styles.settingLabel}>Push notifications</Text>
              <Toggle enabled={pushEnabled} onPress={() => setPushEnabled((enabled) => !enabled)} />
            </View>
            <View style={styles.thresholdHeader}>
              <Text style={styles.settingLabel}>AQI alert threshold</Text>
              <Text style={styles.thresholdValue}>75</Text>
            </View>
            <View style={styles.sliderWrap}>
              <View style={styles.sliderInactive} />
              <LinearGradient
                colors={[colors.goodGreen, colors.moderateYellow, colors.unhealthyOrange]}
                end={{ x: 1, y: 0 }}
                start={{ x: 0, y: 0 }}
                style={styles.sliderActive}
              />
              <View style={styles.sliderKnob} />
            </View>
            <View style={[styles.settingRow, styles.briefingRow]}>
              <Text style={styles.settingLabel}>Daily morning briefing</Text>
              <Toggle enabled={briefingEnabled} onPress={() => setBriefingEnabled((enabled) => !enabled)} />
            </View>
          </ProfileCard>

          <ProfileCard icon="cog-outline" title="App settings">
            <Text style={styles.groupLabel}>Language</Text>
            <View style={styles.segmentRow}>
              {(['FR', 'EN'] as const).map((item) => (
                <SegmentButton
                  key={item}
                  label={item}
                  selected={language === item}
                  onPress={() => setLanguage(item)}
                />
              ))}
            </View>
            <Text style={[styles.groupLabel, styles.themeLabel]}>Theme</Text>
            <View style={styles.segmentRow}>
              {(['System', 'Light', 'Dark'] as const).map((item) => (
                <SegmentButton
                  key={item}
                  label={item}
                  selected={theme === item}
                  onPress={() => setTheme(item)}
                />
              ))}
            </View>
            <Pressable
              accessibilityRole="button"
              onPress={() => navigation.navigate('Settings')}
              style={styles.aboutRow}
            >
              <Text style={styles.aboutText}>About AirPulse</Text>
              <Ionicons color={colors.textSecondary} name="chevron-forward" size={20} />
            </Pressable>
            <Pressable accessibilityRole="button" style={styles.signOutRow}>
              <Text style={styles.signOutText}>Sign out</Text>
              <Ionicons color="#FF3345" name="log-out-outline" size={20} />
            </Pressable>
          </ProfileCard>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function ProfileCard({
  children,
  icon,
  title,
}: {
  children: ReactNode;
  icon: MaterialIconName;
  title: string;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <MaterialCommunityIcons color="#050505" name={icon} size={23} />
        <Text style={styles.cardTitle}>{title}</Text>
      </View>
      <View style={styles.cardBody}>{children}</View>
    </View>
  );
}

function InfoRow({
  label,
  last,
  value,
}: {
  label: string;
  last?: boolean;
  value: ReactNode;
}) {
  return (
    <View style={[styles.infoRow, last && styles.lastInfoRow]}>
      <Text style={styles.infoLabel}>{label}</Text>
      {typeof value === 'string' ? <Text style={styles.infoValue}>{value}</Text> : value}
    </View>
  );
}

function Chip({ label, tone }: { label: string; tone: 'blue' | 'green' | 'orange' }) {
  return (
    <View style={[styles.chip, chipToneStyle(tone)]}>
      <Text style={[styles.chipText, chipTextToneStyle(tone)]}>{label}</Text>
    </View>
  );
}

function Toggle({ enabled, onPress }: { enabled: boolean; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: enabled }}
      onPress={onPress}
      style={[styles.toggle, enabled && styles.toggleEnabled]}
    >
      <View style={[styles.toggleThumb, enabled && styles.toggleThumbEnabled]} />
    </Pressable>
  );
}

function SegmentButton({
  label,
  onPress,
  selected,
}: {
  label: string;
  onPress: () => void;
  selected: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.segmentButton, selected && styles.segmentSelected]}
    >
      <Text style={[styles.segmentText, selected && styles.segmentTextSelected]}>{label}</Text>
    </Pressable>
  );
}

function activityLabel(value: string) {
  return value === 'moderate' ? 'Modéré' : value;
}

function sensitivityLabel(value: string) {
  return value === 'high' ? 'Haute' : value;
}

function chipToneStyle(tone: 'blue' | 'green' | 'orange') {
  if (tone === 'blue') return styles.chipBlue;
  if (tone === 'green') return styles.chipGreen;
  return styles.chipOrange;
}

function chipTextToneStyle(tone: 'blue' | 'green' | 'orange') {
  if (tone === 'blue') return styles.chipBlueText;
  if (tone === 'green') return styles.chipGreenText;
  return styles.chipOrangeText;
}

const styles = StyleSheet.create({
  aboutRow: {
    alignItems: 'center',
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 14,
    paddingBottom: 11,
  },
  aboutText: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 20,
  },
  addLocationButton: {
    alignItems: 'center',
    borderColor: '#A7CCFF',
    borderRadius: 13,
    borderWidth: 1,
    height: 36,
    justifyContent: 'center',
  },
  addLocationText: {
    color: '#0057FF',
    fontSize: 16,
    fontWeight: '700',
  },
  avatar: {
    alignItems: 'center',
    borderRadius: 55,
    height: 110,
    justifyContent: 'center',
    width: 110,
    ...shadows.soft,
  },
  avatarText: {
    color: colors.white,
    fontSize: 31,
    fontWeight: '900',
  },
  bellWrap: {
    position: 'relative',
  },
  briefingRow: {
    marginTop: 11,
  },
  card: {
    backgroundColor: colors.white,
    borderColor: colors.border,
    borderRadius: 18,
    borderWidth: StyleSheet.hairlineWidth,
    overflow: 'hidden',
    ...shadows.card,
  },
  cardBody: {
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  cardHeader: {
    alignItems: 'center',
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    gap: 12,
    minHeight: 58,
    paddingHorizontal: 16,
  },
  cardTitle: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '900',
    letterSpacing: 0,
  },
  cardsPane: {
    backgroundColor: colors.background,
    gap: 14,
    paddingBottom: 82,
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  chip: {
    borderRadius: 12,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  chipBlue: {
    backgroundColor: '#E7F0FF',
  },
  chipBlueText: {
    color: '#0057FF',
  },
  chipGreen: {
    backgroundColor: '#DDFBE9',
  },
  chipGreenText: {
    color: '#05823C',
  },
  chipOrange: {
    backgroundColor: '#FFECD9',
  },
  chipOrangeText: {
    color: '#D64C00',
  },
  chipText: {
    fontSize: 15,
    fontWeight: '700',
    lineHeight: 18,
  },
  chipsRow: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    justifyContent: 'flex-end',
  },
  editButton: {
    alignItems: 'center',
    borderRadius: 17,
    height: 56,
    justifyContent: 'center',
  },
  editButtonText: {
    color: colors.white,
    fontSize: 18,
    fontWeight: '800',
  },
  editButtonWrap: {
    marginTop: 15,
    width: '100%',
  },
  email: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 21,
    marginTop: 4,
  },
  groupLabel: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 21,
  },
  header: {
    alignItems: 'center',
    backgroundColor: colors.white,
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: 12,
    paddingHorizontal: 16,
    paddingTop: 14,
  },
  headerBrand: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 11,
  },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: 20,
    fontWeight: '900',
    letterSpacing: 0,
  },
  infoLabel: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 21,
  },
  infoRow: {
    alignItems: 'center',
    borderBottomColor: colors.border,
    borderBottomWidth: StyleSheet.hairlineWidth,
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 35,
  },
  infoValue: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '700',
    lineHeight: 21,
    textAlign: 'right',
  },
  lastInfoRow: {
    borderBottomWidth: 0,
  },
  locationIconWrap: {
    alignItems: 'center',
    backgroundColor: '#C9E2B8',
    borderRadius: 9,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  locationRow: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 14,
    minHeight: 52,
  },
  locationText: {
    color: colors.textMuted,
    fontSize: 16,
    lineHeight: 21,
  },
  locationsList: {
    gap: 3,
  },
  logo: {
    alignItems: 'center',
    borderRadius: 13,
    height: 38,
    justifyContent: 'center',
    width: 38,
  },
  logoText: {
    color: colors.white,
    fontSize: 17,
    fontWeight: '900',
  },
  name: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 28,
    marginTop: 16,
  },
  notificationDot: {
    backgroundColor: '#FF3345',
    borderColor: colors.white,
    borderRadius: 7,
    borderWidth: 2,
    height: 13,
    position: 'absolute',
    right: -1,
    top: -1,
    width: 13,
  },
  profileHero: {
    alignItems: 'center',
    backgroundColor: colors.white,
    paddingBottom: 28,
    paddingHorizontal: 16,
    paddingTop: 28,
  },
  safeArea: {
    backgroundColor: colors.white,
    flex: 1,
  },
  scrollContent: {
    backgroundColor: colors.white,
  },
  segmentButton: {
    alignItems: 'center',
    backgroundColor: '#F0F2F5',
    borderRadius: 10,
    height: 32,
    justifyContent: 'center',
    minWidth: 54,
    paddingHorizontal: 13,
  },
  segmentRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 7,
  },
  segmentSelected: {
    backgroundColor: '#155CFF',
  },
  segmentText: {
    color: '#4B5567',
    fontSize: 15,
    fontWeight: '800',
  },
  segmentTextSelected: {
    color: colors.white,
  },
  sensitivityPill: {
    backgroundColor: '#FFF0BF',
    borderRadius: 18,
    marginTop: 11,
    paddingHorizontal: 16,
    paddingVertical: 6,
  },
  sensitivityText: {
    color: '#A14B00',
    fontSize: 16,
    fontWeight: '900',
    lineHeight: 19,
  },
  settingLabel: {
    color: colors.textSecondary,
    fontSize: 16,
    lineHeight: 21,
  },
  settingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    minHeight: 33,
  },
  signOutRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 10,
  },
  signOutText: {
    color: '#FF3345',
    fontSize: 16,
    fontWeight: '800',
    lineHeight: 20,
  },
  sliderActive: {
    borderRadius: 4,
    height: 7,
    left: 0,
    position: 'absolute',
    width: '47%',
  },
  sliderInactive: {
    backgroundColor: '#DFE3EA',
    borderRadius: 4,
    height: 7,
    width: '100%',
  },
  sliderKnob: {
    backgroundColor: colors.white,
    borderColor: colors.primaryBlue,
    borderRadius: 12,
    borderWidth: 2,
    height: 24,
    left: '43%',
    position: 'absolute',
    width: 24,
  },
  sliderWrap: {
    alignItems: 'center',
    flexDirection: 'row',
    height: 24,
    marginTop: 2,
    position: 'relative',
  },
  themeLabel: {
    marginTop: 12,
  },
  thresholdHeader: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 2,
  },
  thresholdValue: {
    color: '#246BFF',
    fontSize: 16,
    fontWeight: '900',
    lineHeight: 21,
  },
  toggle: {
    backgroundColor: '#DDE3EC',
    borderRadius: 16,
    height: 30,
    justifyContent: 'center',
    paddingHorizontal: 3,
    width: 54,
  },
  toggleEnabled: {
    backgroundColor: '#3A86F7',
  },
  toggleThumb: {
    backgroundColor: colors.white,
    borderRadius: 12,
    height: 24,
    width: 24,
  },
  toggleThumbEnabled: {
    alignSelf: 'flex-end',
  },
});
