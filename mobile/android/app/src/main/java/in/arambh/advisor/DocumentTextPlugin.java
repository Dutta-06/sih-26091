package in.arambh.advisor;

import android.graphics.Point;
import android.graphics.Rect;
import android.net.Uri;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.devanagari.DevanagariTextRecognizerOptions;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.io.File;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * On-device text recognition for document scans (ML Kit, bundled models: works with no network).
 * Runs the Latin and the Devanagari recognisers and returns the richer result as lines in reading order.
 * The photo is deleted after reading when it lives in the app's cache.
 */
@CapacitorPlugin(name = "DocumentText")
public class DocumentTextPlugin extends Plugin {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @PluginMethod
    public void recognize(PluginCall call) {
        String path = call.getString("path");
        if (path == null || path.isEmpty()) {
            call.reject("path is required");
            return;
        }
        executor.execute(() -> {
            TextRecognizer latin = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            TextRecognizer devanagari = TextRecognition.getClient(new DevanagariTextRecognizerOptions.Builder().build());
            try {
                Uri uri = path.startsWith("file://") || path.startsWith("content://") ? Uri.parse(path) : Uri.fromFile(new File(path));
                InputImage image = InputImage.fromFilePath(getContext(), uri);
                Text a = Tasks.await(latin.process(image));
                Text b = Tasks.await(devanagari.process(image));
                // Devanagari recogniser also reads Latin; keep the Latin one's lines for ASCII-heavy documents
                List<Line> lines = merge(lines(a), lines(b));
                JSArray out = new JSArray();
                for (Line l : lines) out.put(l.text);
                JSObject result = new JSObject();
                result.put("lines", out);
                result.put("width", image.getWidth());
                result.put("height", image.getHeight());
                call.resolve(result);
                if (uri.getPath() != null && uri.getPath().startsWith(getContext().getCacheDir().getPath())) {
                    //noinspection ResultOfMethodCallIgnored
                    new File(uri.getPath()).delete();
                }
            } catch (Exception e) {
                call.reject("Could not read the image", e);
            } finally {
                latin.close();
                devanagari.close();
            }
        });
    }

    private static final class Line {
        final String text;
        final int top;
        final int left;

        Line(String text, int top, int left) {
            this.text = text;
            this.top = top;
            this.left = left;
        }
    }

    private static List<Line> lines(Text text) {
        List<Line> out = new ArrayList<>();
        for (Text.TextBlock block : text.getTextBlocks()) {
            for (Text.Line line : block.getLines()) {
                Rect box = line.getBoundingBox();
                Point[] corners = line.getCornerPoints();
                int top = box != null ? box.top : corners != null && corners.length > 0 ? corners[0].y : 0;
                int left = box != null ? box.left : corners != null && corners.length > 0 ? corners[0].x : 0;
                out.add(new Line(line.getText(), top, left));
            }
        }
        // Reading order: rows (within ~12px) top to bottom, then left to right
        Collections.sort(out, (x, y) -> Math.abs(x.top - y.top) > 12 ? Integer.compare(x.top, y.top) : Integer.compare(x.left, y.left));
        return out;
    }

    /** Devanagari lines where they contain Devanagari, otherwise the Latin recogniser's reading. */
    private static List<Line> merge(List<Line> latin, List<Line> devanagari) {
        List<Line> out = new ArrayList<>(latin);
        for (Line d : devanagari) {
            if (d.text.codePoints().anyMatch(c -> c >= 0x0900 && c <= 0x097F)) out.add(d);
        }
        Collections.sort(out, (x, y) -> Math.abs(x.top - y.top) > 12 ? Integer.compare(x.top, y.top) : Integer.compare(x.left, y.left));
        return out;
    }
}
