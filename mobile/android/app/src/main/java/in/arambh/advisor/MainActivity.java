package in.arambh.advisor;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(DocumentTextPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
