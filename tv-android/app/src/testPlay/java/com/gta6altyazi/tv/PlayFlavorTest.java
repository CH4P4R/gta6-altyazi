// SPDX-License-Identifier: AGPL-3.0-only
// Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz. Modified for GTA6 Altyazı since 2026-11-16.
package com.gta6altyazi.tv;

import static org.junit.Assert.assertFalse;

import org.junit.Test;

/** Google Play paketinde katman modu kapalıdır (TV-TR kuralı; bkz. docs/play-store-tv.md). */
public class PlayFlavorTest {
    @Test
    public void overlayModeIsOff() {
        assertFalse(BuildConfig.OVERLAY_MODE);
    }
}
