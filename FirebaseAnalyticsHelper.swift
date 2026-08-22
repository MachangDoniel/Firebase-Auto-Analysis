//
//  FirebaseAnalyticsHelper.swift
//  Neural Sound iOS Portfolio (Music Separation & Vocal Cleaner)
//
//  Created for clean Firebase & GA4 environment isolation.
//  1. Disables analytics in Xcode DEBUG builds (stops developer event/crash pollution).
//  2. Dynamically tags TestFlight vs Production App Store environments.
//  3. Safely coexists with Firebase App Check.
//

import Foundation
import FirebaseCore
import FirebaseAnalytics

public enum AppEnvironment: String {
    case development = "development"
    case testflight  = "testflight"
    case production  = "production"
}

public struct FirebaseAnalyticsHelper {
    
    /// Detects current runtime environment safely without breaking App Check
    public static var currentEnvironment: AppEnvironment {
        #if DEBUG
        return .development
        #else
        // TestFlight builds use sandbox receipt URL
        let isTestFlight = Bundle.main.appStoreReceiptURL?.lastPathComponent == "sandboxReceipt"
        return isTestFlight ? .testflight : .production
        #endif
    }
    
    /// Configures analytics collection and user properties on app launch
    public static func setupAnalytics() {
        let env = currentEnvironment
        
        #if DEBUG
        // 🚫 DISABLE Analytics in Xcode Debug runs (zero noise/fake purchases in GA4)
        Analytics.setAnalyticsCollectionEnabled(false)
        print("🛑 [FirebaseAnalytics] Analytics DISABLED for Xcode Debug session.")
        #else
        // ✅ ENABLE Analytics in TestFlight & App Store
        Analytics.setAnalyticsCollectionEnabled(true)
        
        // Tag environment dimension in GA4
        Analytics.setUserProperty(env.rawValue, forName: "app_environment")
        
        // Tag app build and version
        if let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String,
           let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String {
            Analytics.setUserProperty("\(version) (\(build))", forName: "app_build_full")
        }
        
        print("🚀 [FirebaseAnalytics] Initialized for environment: \(env.rawValue.uppercased())")
        #endif
    }
}
