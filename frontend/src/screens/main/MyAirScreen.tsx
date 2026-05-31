import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AQICard } from '@/components/aqi/AQICard';
import { ForecastCarousel } from '@/components/aqi/ForecastCarousel';
import { RecommendationCard } from '@/components/aqi/RecommendationCard';
import { WeatherMetrics } from '@/components/aqi/WeatherMetrics';
import { useCurrentAQI } from '@/hooks/useCurrentAQI';
import { usePredictions } from '@/hooks/usePredictions';
import { useRecommendation } from '@/hooks/useRecommendation';
import { mockUser } from '@/mock';
import { colors } from '@/theme';
import { formatDashboardDate } from '@/utils/dateFormat';

const PRIMARY_SENSOR_ID = 'AQ_CST_01';

export function MyAirScreen() {
  const currentAQI = useCurrentAQI(PRIMARY_SENSOR_ID);
  const predictions = usePredictions(PRIMARY_SENSOR_ID);
  const recommendation = useRecommendation(mockUser.user_id, PRIMARY_SENSOR_ID);

  const sensor = currentAQI.data;
  const forecast = predictions.data;
  const dashboardRecommendation = recommendation.data;

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ScrollView
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        <View style={styles.phoneFrame}>
          <View style={styles.header}>
            <View style={styles.brand}>
              <LinearGradient
                colors={[colors.primaryBlue, colors.secondaryCyan]}
                end={{ x: 1, y: 1 }}
                start={{ x: 0, y: 0 }}
                style={styles.logo}
              >
                <Text style={styles.logoText}>AQ</Text>
              </LinearGradient>
              <Text style={styles.appName}>AirPulse</Text>
            </View>

            <View style={styles.headerActions}>
              <Ionicons color={colors.textSecondary} name="search-outline" size={30} />
              <View style={styles.bellWrap}>
                <Ionicons color={colors.textSecondary} name="notifications-outline" size={30} />
                <View style={styles.notificationDot} />
              </View>
              <LinearGradient
                colors={['#5275FF', colors.purpleAccent]}
                end={{ x: 1, y: 1 }}
                start={{ x: 0, y: 0 }}
                style={styles.avatar}
              >
                <Text style={styles.avatarText}>AM</Text>
              </LinearGradient>
            </View>
          </View>

          <View style={styles.locationBlock}>
            <Text style={styles.city}>Algiers</Text>
            <Text style={styles.timestamp}>{formatDashboardDate(sensor.timestamp)}</Text>
          </View>

          <AQICard sensor={sensor} />

          {sensor.weather ? <WeatherMetrics weather={sensor.weather} /> : null}

          <View style={styles.forecastSection}>
            <Text style={styles.sectionTitle}>Hourly forecast</Text>
            <ForecastCarousel current={sensor} points={forecast.predictions} />
          </View>

          <RecommendationCard recommendation={dashboardRecommendation} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  appName: {
    color: colors.textPrimary,
    fontSize: 24,
    fontWeight: '800',
    letterSpacing: 0,
  },
  avatar: {
    alignItems: 'center',
    borderRadius: 20,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  avatarText: {
    color: colors.white,
    fontSize: 19,
    fontWeight: '800',
  },
  bellWrap: {
    position: 'relative',
  },
  brand: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 16,
  },
  city: {
    color: colors.textPrimary,
    fontSize: 26,
    fontWeight: '900',
    letterSpacing: 0,
    lineHeight: 31,
    textAlign: 'center',
  },
  forecastSection: {
    gap: 14,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  headerActions: {
    alignItems: 'center',
    flexDirection: 'row',
    gap: 14,
  },
  locationBlock: {
    alignItems: 'center',
    marginBottom: 2,
    marginTop: 4,
  },
  logo: {
    alignItems: 'center',
    borderRadius: 14,
    height: 40,
    justifyContent: 'center',
    width: 40,
  },
  logoText: {
    color: colors.white,
    fontSize: 18,
    fontWeight: '900',
  },
  notificationDot: {
    backgroundColor: '#FF3345',
    borderColor: colors.white,
    borderRadius: 7,
    borderWidth: 2,
    height: 13,
    position: 'absolute',
    right: -1,
    top: 0,
    width: 13,
  },
  phoneFrame: {
    alignSelf: 'center',
    gap: 12,
    maxWidth: 430,
    paddingHorizontal: 16,
    paddingTop: 16,
    width: '100%',
  },
  safeArea: {
    backgroundColor: colors.white,
    flex: 1,
  },
  scrollContent: {
    backgroundColor: colors.white,
    flexGrow: 1,
    paddingBottom: 120,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 23,
    fontWeight: '800',
    letterSpacing: 0,
    lineHeight: 29,
  },
  timestamp: {
    color: colors.textSecondary,
    fontSize: 20,
    lineHeight: 25,
    marginTop: 6,
    textAlign: 'center',
  },
});
