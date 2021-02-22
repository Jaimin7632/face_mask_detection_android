package org.tensorflow.lite.examples.detection.uartBoard;

import android.os.Build;

public class BoardDefaults {
    private static final String DEVICE_RPI3 = "rpi3";
    private static final String DEVICE_IMX6UL_PICO = "imx6ul_pico";
    private static final String DEVICE_IMX7D_PICO = "imx7d_pico";
    private static final String DEVICE_RK3288 = "rk3288";


    /**
     * Return the UART for loopback.
     */
    public static String getUartName() {
        switch (Build.DEVICE)
        {
            case DEVICE_RPI3:
                return "UART0";
            case DEVICE_IMX6UL_PICO:
                return "UART3";
            case DEVICE_IMX7D_PICO:
                return "UART6";
            case DEVICE_RK3288:
                return "UART0";
            default:
                throw new IllegalStateException("Unknown Build.DEVICE " + Build.DEVICE);
        }
    }
}
