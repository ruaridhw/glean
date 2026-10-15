import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing (docs/ANDROID_TEST_DISTRIBUTION.md). Codemagic's
// `android-test-distribution` workflow writes the release JKS to
// CM_KEYSTORE_PATH and supplies its passwords and alias as CM_* variables.
// Locally, a gitignored `key.properties` works too. With neither (GitHub CI,
// the integration jobs, most checkouts) release builds fall back to debug
// signing so they still produce something installable; Codemagic's signature
// check refuses to distribute such a build.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(keystorePropertiesFile.inputStream())
}

fun requiredEnv(name: String): String =
    System.getenv(name)?.takeIf { it.isNotBlank() }
        ?: error("$name must be set when CM_KEYSTORE_PATH is")

val ciKeystorePath: String? = System.getenv("CM_KEYSTORE_PATH")?.takeIf { it.isNotBlank() }
val hasReleaseKeystore = ciKeystorePath != null || keystorePropertiesFile.exists()

android {
    namespace = "com.ruaridhw.glean"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Matches the iOS bundle identifier set in `ios/fastlane/Appfile` and
        // `Runner.xcodeproj` — the RN app had no iOS identifier at all, so
        // this Flutter port is what first makes the two match (AC-BUILD-10).
        applicationId = "com.ruaridhw.glean"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        if (hasReleaseKeystore) {
            create("release") {
                if (ciKeystorePath != null) {
                    storeFile = file(requiredEnv("CM_KEYSTORE_PATH"))
                    storePassword = requiredEnv("CM_KEYSTORE_PASSWORD")
                    keyAlias = requiredEnv("CM_KEY_ALIAS")
                    keyPassword = requiredEnv("CM_KEY_PASSWORD")
                } else {
                    storeFile = file(keystoreProperties.getProperty("storeFile"))
                    storePassword = keystoreProperties.getProperty("storePassword")
                    keyAlias = keystoreProperties.getProperty("keyAlias")
                    keyPassword = keystoreProperties.getProperty("keyPassword")
                }
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasReleaseKeystore) {
                signingConfigs.getByName("release")
            } else {
                // No release keystore here: debug-signed (see the comment above).
                signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
