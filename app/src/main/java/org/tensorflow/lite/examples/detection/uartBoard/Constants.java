package org.tensorflow.lite.examples.detection.uartBoard;

import org.tensorflow.lite.examples.detection.BuildConfig;

public class Constants {

    // values have to be globally unique
    public  static final String INTENT_ACTION_GRANT_USB = BuildConfig.APPLICATION_ID + ".GRANT_USB";
    public  static final String INTENT_ACTION_DISCONNECT = BuildConfig.APPLICATION_ID + ".Disconnect";
    public  static final String NOTIFICATION_CHANNEL = BuildConfig.APPLICATION_ID + ".Channel";
    public  static final String INTENT_CLASS_MAIN_ACTIVITY = BuildConfig.APPLICATION_ID + ".MainActivity";
    public  static final int device_id = 1003;
    public  static final int portNumber = 0;
    public  static final int boadRate = 115200;

    // values have to be unique within each app
    public  static final int NOTIFY_MANAGER_START_FOREGROUND_SERVICE = 1001;

    private Constants() {}
}
