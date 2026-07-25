import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Release signing (FLUTTER_MIGRATION.md §8, AC-CI-04/05). `key.properties` is
// generated once on the release Mac (`keytool` + this file, per Flutter's own
// Android deployment docs) and deliberately gitignored — see `app/.gitignore`
// and `app/android/fastlane/Fastfile`. Its absence (every CI job, and any
// local checkout without it) falls back to debug signing so `flutter build`/
// `flutter run --release` and the workflow_dispatch integration jobs keep
// working without it; only the actual Play-upload lane needs it configured.
val keystoreProperties = Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
val hasReleaseKeystore = keystorePropertiesFile.exists()
if (hasReleaseKeystore) {
    keystoreProperties.load(keystorePropertiesFile.inputStream())
}

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
                storeFile = file(keystoreProperties.getProperty("storeFile"))
                storePassword = keystoreProperties.getProperty("storePassword")
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasReleaseKeystore) {
                signingConfigs.getByName("release")
            } else {
                // No real upload keystore on this machine — debug-signed so
                // `flutter build`/`flutter run --release` and the CI
                // integration jobs still produce something installable.
                // Never uploaded anywhere real like this: `fastlane`'s
                // Android lane only runs on the Mac that has `key.properties`.
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
