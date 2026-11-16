// SPDX-License-Identifier: AGPL-3.0-only
// Based on CouchSubs (https://github.com/yorulmazsinan/couchsubs), Copyright (C) 2026 Sinan Yorulmaz. Modified for GTA6 Altyazı since 2026-11-16.
package com.gta6altyazi.tv;

import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** Masaüstünün kurduğu APK'da katman modu açıktır (siyah ekran sorunu olan TV'ler için). */
public class SideloadFlavorTest {
    @Test
    public void overlayModeIsOn() {
        assertTrue(BuildConfig.OVERLAY_MODE);
    }
}
