plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
}

android {
    namespace = "com.yourcompany.signagefiretv"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.yourcompany.signagefiretv"
        minSdk = 22  // Fire OS 7+
        targetSdk = 34
        versionCode = 2
        versionName = "1.0.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
    }

    signingConfigs {
        create("release") {
            // Uses env vars or Gradle properties; safe defaults keep debug builds working.
            val storeFilePath = System.getenv("SIGNING_STORE_FILE")
                ?: (project.findProperty("SIGNING_STORE_FILE") as String?)
            val storePasswordValue = System.getenv("SIGNING_STORE_PASSWORD")
                ?: (project.findProperty("SIGNING_STORE_PASSWORD") as String?)
            val keyAliasValue = System.getenv("SIGNING_KEY_ALIAS")
                ?: (project.findProperty("SIGNING_KEY_ALIAS") as String?)
            val keyPasswordValue = System.getenv("SIGNING_KEY_PASSWORD")
                ?: (project.findProperty("SIGNING_KEY_PASSWORD") as String?)

            if (!storeFilePath.isNullOrBlank()) {
                storeFile = file(storeFilePath)
            }
            if (!storePasswordValue.isNullOrBlank()) {
                storePassword = storePasswordValue
            }
            if (!keyAliasValue.isNullOrBlank()) {
                keyAlias = keyAliasValue
            }
            if (!keyPasswordValue.isNullOrBlank()) {
                keyPassword = keyPasswordValue
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }

    kotlinOptions {
        jvmTarget = "1.8"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.material)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.lifecycle.runtime.ktx)

    // Media3 for video playback
    implementation("androidx.media3:media3-exoplayer:1.2.1")
    implementation("androidx.media3:media3-ui:1.2.1")

    // Glide for image loading
    implementation(libs.glide)

    // Coroutines
    implementation(libs.kotlinx.coroutines.android)

    // Testing
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
}
