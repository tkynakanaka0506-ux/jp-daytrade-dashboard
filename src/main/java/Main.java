import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;

import java.io.File;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.text.DecimalFormat;
import java.text.DecimalFormatSymbols;
import java.time.Duration;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Ã¦ÂÂ¥Ã¦ÂÂ¬Ã¦Â Âª(Ã¦ÂÂ±Ã¨Â¨Â¼)Ã£ÂÂÃ£ÂÂ¤Ã£ÂÂÃ£ÂÂ¬Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ·Ã£ÂÂ¥Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂÃ§ÂÂ¨Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ¿Ã¦ÂÂ´Ã¦ÂÂ°Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ«Ã£ÂÂ
 *
 * Ã£ÂÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ­Ã£ÂÂ°Ã£ÂÂ©Ã£ÂÂ Ã£ÂÂ Ã£ÂÂÃ£ÂÂ§ data.json Ã£ÂÂÃ£ÂÂÃ¦Â±ÂºÃ¥Â®ÂÃ¨Â«ÂÃ§ÂÂÃ£ÂÂ«Ã£ÂÂÃ¦ÂÂ´Ã¦ÂÂ°Ã£ÂÂÃ£ÂÂ(WebSearchÃ§Â­ÂÃ£ÂÂ§LLMÃ£ÂÂ
 * Ã¦ÂÂÃ¥ÂÂÃ£ÂÂ§Ã¦ÂÂÃ¥Â Â±Ã¥ÂÂÃ©ÂÂÃ£ÂÂÃ£ÂÂÃ¤Â»Â£Ã£ÂÂÃ£ÂÂÃ£ÂÂ«Ã£ÂÂÃ§ÂÂ¡Ã¦ÂÂÃ£ÂÂ»Ã£ÂÂ­Ã£ÂÂ¼Ã¤Â¸ÂÃ¨Â¦ÂÃ£ÂÂ®Ã¥ÂÂ¬Ã©ÂÂÃ£ÂÂ½Ã£ÂÂ¼Ã£ÂÂ¹Ã£ÂÂÃ§ÂÂ´Ã¦ÂÂ¥HTTPÃ£ÂÂ§Ã¥ÂÂÃ¥Â¾ÂÃ£ÂÂÃ£ÂÂ)Ã£ÂÂ
 * HTMLÃ§ÂÂÃ¦ÂÂÃ£ÂÂ¯Ã¦ÂÂ¢Ã¥Â­ÂÃ£ÂÂ® render_dashboard.py Ã£ÂÂ«Ã£ÂÂÃ£ÂÂ®Ã£ÂÂ¾Ã£ÂÂ¾Ã¤Â»Â»Ã£ÂÂÃ£ÂÂ(Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂ¼Ã£ÂÂ¯Ã¤Â¸ÂÃ¨Â¦ÂÃ£ÂÂ®Pure Python)Ã£ÂÂ
 *
 * Ã¤Â½Â¿Ã£ÂÂÃ¦ÂÂ¹: java -jar dashboard-updater.jar <morning|evening> <data.jsonÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ¹>
 */
public class Main {

    private static final String UA =
        "Mozilla/5.0 (compatible; jp-daytrade-dashboard-bot/1.0; " +
        "+https://github.com/tkynakanaka0506-ux/jp-daytrade-dashboard)";

    private static final HttpClient HTTP = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(15))
        .build();

    private static final ObjectMapper MAPPER = new ObjectMapper();

    // Ã¥Â®ÂÃ§ÂÂ¹Ã¨Â¦Â³Ã¦Â¸Â¬Ã£ÂÂÃ£ÂÂÃ¥ÂÂÃ¥ÂÂ¥Ã©ÂÂÃ¦ÂÂÃ£ÂÂÃ¥Â¢ÂÃ¦Â¸ÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ¥Â Â´Ã¥ÂÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ§Â·Â¨Ã©ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ Ã£ÂÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂÃ£ÂÂ
    private static final String[][] WATCHLIST = {
        // --- 基本4銘柄 ---
        {"7203", "トヨタ自動車"},
        {"6758", "ソニーグループ"},
        {"8306", "三菱UFJフィナンシャル・グループ"},
        {"9984", "ソフトバンクグループ"},
        // --- 追加銘柄 (watchlist.json で上書き可能) ---
        {"6861", "キーエンス"},
        {"6954", "ファナック"},
        {"7974", "任天堂"},
        {"6098", "リクルートホールディングス"},
        {"8035", "東京エレクトロン"},
        {"9433", "KDDI"},
        {"9432", "日本電信電話"},
        {"7267", "本田技研工業"},
        {"6367", "ダイキン工業"},
        {"9983", "ファーストリテイリング"},
        {"4063", "信越化学工業"},
        {"6857", "アドバンテスト"},
        {"4519", "中外製薬"},
        {"5401", "日本製鉄"},
        {"2413", "エムスリー"},
        {"6645", "オムロン"},
    };

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "morning"; // "morning" or "evening"
        File dataFile = new File(args.length > 1 ? args[1] : "data.json");

        ObjectNode root = (ObjectNode) MAPPER.readTree(dataFile);

        ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
        root.put("generated_at", nowJst.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        root.put("run_type", mode);

        // ---- Ã¥Â¸ÂÃ¥Â Â´Ã¦ÂÂÃ¦Â¨Â(Ã§ÂÂ¡Ã¦ÂÂÃ£ÂÂ»Ã£ÂÂ­Ã£ÂÂ¼Ã¤Â¸ÂÃ¨Â¦ÂÃ£ÂÂ®Yahoo Finance chart APIÃ£ÂÂÃ£ÂÂÃ¥ÂÂÃ¥Â¾Â) ----
        updateNested(root, "us_market", "sp500", "^GSPC", false);
        updateNested(root, "us_market", "dow", "^DJI", false);
        updateNested(root, "us_market", "nasdaq", "^IXIC", false);
        updateNested(root, "us_market", "sox", "^SOX", false);
        updateTopLevel(root, "fx", "JPY=X", true);
        updateTopLevel(root, "nikkei225", "^N225", false);
        updateTopLevel(root, "nikkei_futures", "NIY=F", false); // Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂÃ£ÂÂ¨Ã£ÂÂÃ£ÂÂ©Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ¥ÂÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂÃ£ÂÂ°Ã¦ÂÂ¢Ã¥Â­ÂÃ¥ÂÂ¤Ã£ÂÂÃ¤Â¿ÂÃ¦ÂÂ

        // ---- TDnetÃ©ÂÂ©Ã¦ÂÂÃ©ÂÂÃ§Â¤Âº(Ã¦Â ÂªÃ¦ÂÂ¢Ã£ÂÂ¢Ã£ÂÂÃ£ÂÂ¤Ã£ÂÂ«Ã§ÂÂÃ£ÂÂÃ£ÂÂ©Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂ¯Ã£ÂÂ¬Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ³Ã£ÂÂ°) ----
        try {
            ArrayNode disclosures = scrapeKabutanDisclosures(3);
            if (disclosures.size() > 0) {
                root.set("evening".equals(mode) ? "tdnet_afterclose" : "tdnet_morning", disclosures);
            }
        } catch (Exception e) {
            System.err.println("[WARN] kabutan disclosures fetch failed: " + e);
        }

        // ---- Ã¥ÂÂÃ¥ÂÂ¥Ã©ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂ«Ã£ÂÂ«Ã¥ÂÂÃ¦ÂÂ(Ã¦ÂÂÃ¨Â³ÂÃ£ÂÂ®Ã¦Â£Â®Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂ¯Ã£ÂÂ¬Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ³Ã£ÂÂ°) ----
        // ---- ウォッチリスト読み込み(watchlist.json があればそちらを優先) ----
        String[][] watchlist = loadWatchlist(dataFile.getParentFile(), WATCHLIST);

        ArrayNode technical = MAPPER.createArrayNode();
        for (String[] w : watchlist) {
            try {
                technical.add(scrapeTechnical(w[0], w[1]));
            } catch (Exception e) {
                System.err.println("[WARN] technical fetch failed for " + w[0] + ": " + e);
            }
        }
        if (technical.size() > 0) {
            root.set("technical", technical);
        }

        // ---- Ã¦ÂÂÃ©ÂÂ·Ã¦Â ÂªÃ¥ÂÂÃ¨Â£Â(TDnetÃ£ÂÂÃ¦Â¥Â­Ã§Â¸Â¾Ã¤ÂºÂÃ¦ÂÂ³Ã£ÂÂ®Ã¤Â¿Â®Ã¦Â­Â£Ã£ÂÂÃ©ÂÂÃ§Â¤ÂºÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ¡Ã¥Â¥Â½Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ®Ã£ÂÂ¿Ã£ÂÂÃ¦Â©ÂÃ¦Â¢Â°Ã§ÂÂÃ£ÂÂ«Ã¦ÂÂ½Ã¥ÂÂº) ----
        try {
            ArrayNode growth = scrapeGrowthCandidates(8, 8);
            if (growth.size() > 0) {
                root.set("growth_candidates", growth);
            }
        } catch (Exception e) {
            System.err.println("[WARN] growth candidates fetch failed: " + e);
        }

        // Ã¦Â³Â¨: overnight_news / afterclose_news / movers_morning / movers_afterclose Ã£ÂÂ¯
        // Ã£ÂÂÃ¨Â©Â±Ã©Â¡ÂÃ¦ÂÂ§Ã£ÂÂ®Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¥Ã£ÂÂ¼Ã£ÂÂ¹Ã£ÂÂ»Ã©ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂÃ©ÂÂ¸Ã£ÂÂ¶Ã¦ÂÂ§Ã¨Â³ÂªÃ¤Â¸ÂÃ£ÂÂÃ§ÂÂ¡Ã¦ÂÂÃ£ÂÂ®Ã¦Â±ÂºÃ¥Â®ÂÃ¨Â«ÂÃ§ÂÂAPIÃ£ÂÂ Ã£ÂÂÃ£ÂÂ§Ã£ÂÂ¯Ã¥ÂÂÃ§ÂÂ¾Ã£ÂÂ§Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂÃ£ÂÂ
        // Ã£ÂÂÃ£ÂÂ®JavaÃ§ÂÂÃ£ÂÂ§Ã£ÂÂ¯Ã¦ÂÂ´Ã¦ÂÂ°Ã¥Â¯Â¾Ã¨Â±Â¡Ã¥Â¤Â(Ã¦ÂÂ¢Ã¥Â­ÂÃ£ÂÂ®Ã¥ÂÂ¤Ã£ÂÂÃ£ÂÂÃ£ÂÂ®Ã£ÂÂ¾Ã£ÂÂ¾Ã¤Â¿ÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ)Ã£ÂÂ
        // Ã£ÂÂÃ£ÂÂ¥Ã£ÂÂ¼Ã£ÂÂ¹APIÃ§Â­ÂÃ£ÂÂÃ¥Â°ÂÃ¥ÂÂ¥Ã£ÂÂÃ£ÂÂÃ¥Â Â´Ã¥ÂÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂ­Ã£ÂÂ¼Ã£ÂÂGitHub SecretsÃ£ÂÂ«Ã§ÂÂ»Ã©ÂÂ²Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ§Ã¨ÂªÂ­Ã£ÂÂ¿Ã¨Â¾Â¼Ã£ÂÂÃ¥Â½Â¢Ã£ÂÂ«Ã¦ÂÂ¡Ã¥Â¼ÂµÃ£ÂÂÃ£ÂÂÃ£ÂÂ

        MAPPER.writerWithDefaultPrettyPrinter().writeValue(dataFile, root);
        System.out.println("[OK] data.json updated (mode=" + mode + ")");
    }

    // ---------------- Ã¥Â¸ÂÃ¥Â Â´Ã¦ÂÂÃ¦Â¨Â ----------------

    /** us_market.sp500 Ã£ÂÂ®Ã£ÂÂÃ£ÂÂÃ£ÂÂª1Ã©ÂÂÃ¥Â±Â¤Ã£ÂÂÃ£ÂÂ¹Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂ¸Ã£ÂÂ§Ã£ÂÂ¯Ã£ÂÂÃ£ÂÂÃ¦ÂÂ´Ã¦ÂÂ°Ã£ÂÂÃ£ÂÂ */
    private static void updateNested(ObjectNode root, String parentField, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // Ã¥Â¤Â±Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ¯Ã¦ÂÂ¢Ã¥Â­ÂÃ¥ÂÂ¤Ã£ÂÂÃ¤Â¿ÂÃ¦ÂÂ
        ObjectNode parent = root.has(parentField) && root.get(parentField).isObject()
            ? (ObjectNode) root.get(parentField)
            : MAPPER.createObjectNode();
        parent.set(field, target);
        root.set(parentField, parent);
    }

    /** fx / nikkei225 / nikkei_futures Ã£ÂÂ®Ã£ÂÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¬Ã£ÂÂÃ£ÂÂ«Ã§ÂÂ´Ã¤Â¸ÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ£Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂÃ£ÂÂÃ¦ÂÂ´Ã¦ÂÂ°Ã£ÂÂÃ£ÂÂ */
    private static void updateTopLevel(ObjectNode root, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // Ã¥Â¤Â±Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ¯Ã¦ÂÂ¢Ã¥Â­ÂÃ¥ÂÂ¤Ã£ÂÂÃ¤Â¿ÂÃ¦ÂÂ
        root.set(field, target);
    }

    private static boolean fillQuote(ObjectNode target, String symbol, boolean isFx) {
        try {
            // "^"Ã£ÂÂ¯RFC3986Ã¤Â¸ÂÃ£ÂÂÃ£ÂÂ¹Ã¤Â¸Â­Ã£ÂÂ®Ã¥ÂÂÃ¦Â³ÂÃ¦ÂÂÃ¥Â­ÂÃ£ÂÂ§Ã£ÂÂ¯Ã£ÂÂªÃ£ÂÂURI.create()Ã£ÂÂÃ¤Â¾ÂÃ¥Â¤ÂÃ£ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ
            // ^GSPC/^DJI/^IXIC/^N225Ã§Â­ÂÃ£ÂÂ®Ã£ÂÂ¤Ã£ÂÂ³Ã£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂ¹Ã£ÂÂ·Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ«Ã£ÂÂ¯Ã¤ÂºÂÃ¥ÂÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ»Ã£ÂÂ³Ã£ÂÂÃ£ÂÂ¨Ã£ÂÂ³Ã£ÂÂ³Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ
            String encodedSymbol = symbol.replace("^", "%5E");
            String url = "https://query1.finance.yahoo.com/v8/finance/chart/" + encodedSymbol + "?interval=1d&range=5d";
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .header("User-Agent", UA)
                .timeout(Duration.ofSeconds(15))
                .GET().build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) return false;

            JsonNode json = MAPPER.readTree(res.body());
            JsonNode result = json.path("chart").path("result").get(0);
            if (result == null || result.isMissingNode()) return false;
            JsonNode meta = result.path("meta");

            double price = meta.path("regularMarketPrice").asDouble(Double.NaN);

            // Ã¦Â³Â¨: meta.chartPreviousCloseÃ£ÂÂ¯Ã£ÂÂrangeÃ¥Â¼ÂÃ¦ÂÂ°(Ã£ÂÂÃ£ÂÂÃ£ÂÂ§Ã£ÂÂ¯5d)Ã£ÂÂ®Ã£ÂÂÃ£ÂÂ£Ã£ÂÂ¼Ã£ÂÂÃ©ÂÂÃ¥Â§ÂÃ¦ÂÂ¥Ã£ÂÂÃ£ÂÂÃ¥ÂÂÃ£ÂÂ®Ã§ÂµÂÃ¥ÂÂ¤Ã£ÂÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂÃ£ÂÂ
            // Ã§ÂÂ´Ã¨Â¿ÂÃ£ÂÂ®Ã¥ÂÂ¶Ã¦Â¥Â­Ã¦ÂÂ¥Ã£ÂÂ®Ã§ÂµÂÃ¥ÂÂ¤Ã£ÂÂ¨Ã£ÂÂ¯Ã§ÂÂ°Ã£ÂÂªÃ£ÂÂ(Ã¤Â¾Â: Ã©ÂÂ±Ã¦ÂÂ«Ã£ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ¨1Ã©ÂÂ±Ã©ÂÂÃ¨Â¿ÂÃ£ÂÂÃ¥ÂÂÃ£ÂÂ®Ã¥ÂÂ¤Ã£ÂÂ«Ã£ÂÂªÃ£ÂÂÃ¥Â¾ÂÃ£ÂÂ)Ã£ÂÂ
            // Ã£ÂÂ¾Ã£ÂÂÃ¥Â®ÂÃ©ÂÂÃ£ÂÂ«Ã£ÂÂ¯meta.previousCloseÃ£ÂÂÃ£ÂÂ£Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂÃ¨ÂÂªÃ¤Â½ÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ®APIÃ£ÂÂ®Ã£ÂÂ¬Ã£ÂÂ¹Ã£ÂÂÃ£ÂÂ³Ã£ÂÂ¹Ã£ÂÂ«Ã¥ÂÂ«Ã£ÂÂ¾Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ£ÂÂÃ£ÂÂ¨Ã£ÂÂÃ¥Â¤ÂÃ£ÂÂÃ£ÂÂ
            // Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂªÃ¥ÂÂÃ¦ÂÂ¡Ã¤Â»Â¶Ã£ÂÂ«Ã£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ¥Â®ÂÃ¨Â³ÂªÃ§ÂÂÃ£ÂÂ«chartPreviousCloseÃ£ÂÂ¸Ã£ÂÂÃ£ÂÂ©Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂÃ§Â¶ÂÃ£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂ¾Ã£ÂÂÃ£ÂÂ
            // Ã£ÂÂÃ£ÂÂÃ£ÂÂ§Ã£ÂÂÃ¥ÂÂÃ¥ÂÂ¶Ã¦Â¥Â­Ã¦ÂÂ¥Ã¦Â¯ÂÃ£ÂÂÃ£ÂÂ«Ã£ÂÂ¯Ã£ÂÂÃ¦ÂÂ¥Ã¦Â¬Â¡Ã£ÂÂ­Ã£ÂÂ¼Ã£ÂÂ½Ã£ÂÂ¯Ã¨Â¶Â³Ã©ÂÂÃ¥ÂÂ(indicators.quote[0].close)Ã£ÂÂ®
            // Ã£ÂÂÃ§ÂÂ´Ã¨Â¿ÂÃ£ÂÂÃ£ÂÂ2Ã§ÂÂªÃ§ÂÂ®Ã£ÂÂ®Ã§ÂµÂÃ¥ÂÂ¤Ã£ÂÂÃ£ÂÂÃ¤Â½Â¿Ã£ÂÂÃ£ÂÂÃ©ÂÂÃ¥ÂÂÃ£ÂÂ®Ã¦ÂÂÃ¥Â¾ÂÃ£ÂÂ®Ã¨Â¦ÂÃ§Â´Â Ã£ÂÂ¯Ã§ÂÂ´Ã¨Â¿ÂÃ£ÂÂ®Ã¥ÂÂÃ¥Â¼ÂÃ¦ÂÂ¥(=regularMarketPriceÃ£ÂÂ®Ã¦ÂÂ¥)Ã£ÂÂ®
            // Ã§ÂµÂÃ¥ÂÂ¤(Ã¥ÂÂÃ¥Â¼ÂÃ¦ÂÂÃ©ÂÂÃ¤Â¸Â­Ã£ÂÂ¯Ã¦ÂÂªÃ§Â¢ÂºÃ¥Â®ÂÃ£ÂÂ§nullÃ£ÂÂ®Ã¥Â Â´Ã¥ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ)Ã£ÂÂÃ£ÂÂÃ£ÂÂ®1Ã£ÂÂ¤Ã¥ÂÂÃ£ÂÂÃ¦Â­Â£Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂÃ¥ÂÂ¶Ã¦Â¥Â­Ã¦ÂÂ¥Ã£ÂÂ®Ã§ÂµÂÃ¥ÂÂ¤Ã£ÂÂÃ£ÂÂ«Ã£ÂÂªÃ£ÂÂÃ£ÂÂ
            double prevClose = Double.NaN;
            JsonNode closesNode = result.path("indicators").path("quote").get(0).path("close");
            if (closesNode.isArray()) {
                List<Double> closes = new java.util.ArrayList<>();
                for (JsonNode c : closesNode) {
                    if (c.isNumber()) closes.add(c.asDouble());
                }
                if (closes.size() >= 2) {
                    prevClose = closes.get(closes.size() - 2);
                }
            }
            // Ã¤Â¸ÂÃ¤Â¸ÂÃ¦ÂÂ¥Ã¦Â¬Â¡Ã§ÂµÂÃ¥ÂÂ¤Ã©ÂÂÃ¥ÂÂÃ£ÂÂÃ¥ÂÂÃ¥Â¾ÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ¥Â Â´Ã¥ÂÂÃ£ÂÂ®Ã£ÂÂ¿Ã£ÂÂÃ¥Â¾ÂÃ¦ÂÂ¥Ã£ÂÂ®chartPreviousCloseÃ£ÂÂ«Ã£ÂÂÃ£ÂÂ©Ã£ÂÂ¼Ã£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂ
            // (Ã§Â²Â¾Ã¥ÂºÂ¦Ã£ÂÂ¯Ã¨ÂÂ½Ã£ÂÂ¡Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂ¤Ã£ÂÂÃ¤Â¸Â¸Ã£ÂÂÃ£ÂÂ¨Ã¨Â«Â¦Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¯Ã¨ÂÂ¯Ã£ÂÂ)Ã£ÂÂ
            if (Double.isNaN(prevClose)) prevClose = meta.path("chartPreviousClose").asDouble(Double.NaN);
            if (Double.isNaN(price) || Double.isNaN(prevClose) || prevClose == 0) return false;

            double changePct = (price - prevClose) / prevClose * 100.0;

            DecimalFormat df = new DecimalFormat("#,##0.00", new DecimalFormatSymbols(Locale.US));
            String valueStr = df.format(price) + (isFx ? "Ã¥ÂÂ" : "");

            String marketState = meta.path("marketState").asText("CLOSED");
            String stateLabel = switch (marketState) {
                case "REGULAR" -> "Ã§ÂÂ¾Ã¥ÂÂ¨Ã¥ÂÂ¤";
                case "PRE" -> "Ã£ÂÂÃ£ÂÂ¬Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ±Ã£ÂÂÃ£ÂÂ";
                case "POST" -> "Ã£ÂÂ¢Ã£ÂÂÃ£ÂÂ¿Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂ¼Ã£ÂÂ±Ã£ÂÂÃ£ÂÂ";
                default -> "Ã§ÂµÂÃ¥ÂÂ¤";
            };
            // Ã¦Â³Â¨: Ã¦ÂÂ¥Ã¤Â»ÂÃ£ÂÂ©Ã£ÂÂÃ£ÂÂ«Ã£ÂÂ«Ã£ÂÂ¯Ã£ÂÂÃ¥ÂÂÃ¥Â¾ÂÃ£ÂÂÃ£ÂÂÃ¤Â»ÂÃ£ÂÂÃ£ÂÂ®Ã§ÂÂ¬Ã©ÂÂÃ£ÂÂÃ£ÂÂ§Ã£ÂÂ¯Ã£ÂÂªÃ£ÂÂÃ£ÂÂÃ¥Â®ÂÃ©ÂÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂ®Ã¥ÂÂ¤Ã£ÂÂÃ¨Â¦Â³Ã¦Â¸Â¬Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¦ÂÂÃ¥ÂÂ»
            // (meta.regularMarketTimeÃ£ÂÂÃ¥ÂÂÃ¥Â¼ÂÃ¤Â¸Â­Ã£ÂÂ®Ã¦ÂÂÃ¦Â¨ÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂ®Ã¦ÂÂÃ§ÂÂ¹Ã£ÂÂÃ¥ÂÂÃ¥Â¼ÂÃ§ÂµÂÃ¤ÂºÂÃ¥Â¾ÂÃ£ÂÂ®Ã¦ÂÂÃ¦Â¨ÂÃ£ÂÂ¯Ã§ÂÂ´Ã¨Â¿ÂÃ§ÂµÂÃ¥ÂÂ¤Ã£ÂÂ®Ã¦ÂÂÃ¥ÂÂ»)Ã£ÂÂÃ¤Â½Â¿Ã£ÂÂÃ£ÂÂ
            // Ã¥ÂÂÃ¦ÂÂ¥Ã£ÂÂÃ§Â¥ÂÃ¦ÂÂ¥Ã£ÂÂ«Ã£ÂÂ¸Ã£ÂÂ§Ã£ÂÂÃ£ÂÂÃ¨ÂµÂ°Ã£ÂÂÃ£ÂÂÃ£ÂÂ¦Ã£ÂÂÃ£ÂÂÃ¥Â®ÂÃ©ÂÂÃ£ÂÂ®Ã¦ÂÂÃ§ÂµÂÃ¥ÂÂÃ¥Â¼ÂÃ¦ÂÂ¥Ã£ÂÂ®Ã¦ÂÂ¥Ã¤Â»ÂÃ£ÂÂÃ¦Â­Â£Ã£ÂÂÃ£ÂÂÃ¨Â¡Â¨Ã§Â¤ÂºÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ
            long regularMarketTime = meta.path("regularMarketTime").asLong(0);
            ZonedDateTime dataTimeJst = regularMarketTime > 0
                ? ZonedDateTime.ofInstant(java.time.Instant.ofEpochSecond(regularMarketTime), ZoneId.of("Asia/Tokyo"))
                : ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
            String asof = dataTimeJst.format(DateTimeFormatter.ofPattern("M/d")) + stateLabel;

            target.put("value", valueStr);
            target.put("change_pct", Math.round(changePct * 100) / 100.0);
            target.put("asof", asof);
            return true;
        } catch (Exception e) {
            System.err.println("[WARN] quote fetch failed for " + symbol + ": " + e);
            return false;
        }
    }

    // ---------------- TDnetÃ©ÂÂ©Ã¦ÂÂÃ©ÂÂÃ§Â¤Âº ----------------

    private static ArrayNode scrapeKabutanDisclosures(int maxPages) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)Ã£ÂÂ(.*?)\\s*(Ã¦Â±ÂºÃ§Â®Â|Ã©ÂÂÃ¥Â½Â|Ã¦Â¥Â­Ã¤Â¿Â®|Ã¨ÂÂªÃ§Â¤Â¾|Ã£ÂÂ¨Ã£ÂÂ¯|Ã¨Â¿Â½Ã¨Â¨Â|Ã¤Â»Â)?\\s*(Ã¤Â»ÂÃ¦ÂÂ¥|Ã¦ÂÂÃ¦ÂÂ¥|\\d{1,2}/\\d{1,2})\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
        );
        int collected = 0;
        for (int page = 1; page <= maxPages && collected < 20; page++) {
            String url = "https://s.kabutan.jp/disclosures/" + (page == 1 ? "" : "?page=" + page);
            Document doc;
            try {
                doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
            } catch (Exception e) {
                System.err.println("[WARN] kabutan page " + page + " fetch failed: " + e);
                break;
            }
            // Ã©ÂÂÃ§Â¤ÂºPDFÃ£ÂÂ¸Ã£ÂÂ®Ã§ÂÂ´Ã£ÂÂªÃ£ÂÂ³Ã£ÂÂ¯Ã£ÂÂ Ã£ÂÂÃ£ÂÂÃ¥Â¯Â¾Ã¨Â±Â¡Ã£ÂÂ«Ã£ÂÂÃ£ÂÂ(Ã£ÂÂÃ£ÂÂÃ£ÂÂ²Ã£ÂÂ¼Ã£ÂÂ·Ã£ÂÂ§Ã£ÂÂ³Ã§Â­ÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ¤Ã£ÂÂºÃ£ÂÂÃ¨ÂÂªÃ§ÂÂ¶Ã£ÂÂ«Ã©ÂÂ¤Ã¥Â¤ÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂ)
            List<Element> links = doc.select("a[href^=https://tdnet-pdf.kabutan.jp/]");
            if (links.isEmpty()) break;
            for (Element a : links) {
                if (collected >= 20) break;
                String text = a.text().trim();
                Matcher m = rowPattern.matcher(text);
                ObjectNode row = MAPPER.createObjectNode();
                if (m.matches()) {
                    row.put("time", m.group(5));
                    row.put("code", "Ã¢ÂÂ");
                    row.put("company", m.group(1).trim());
                    row.put("title", m.group(2).trim());
                    row.put("url", a.absUrl("href"));
                    row.put("tag", m.group(3) != null ? m.group(3) : "Ã¤Â»Â");
                } else {
                    // Ã¦ÂÂ³Ã¥Â®ÂÃ¥Â¤ÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ©Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ®Ã¨Â¡ÂÃ£ÂÂ¯Ã£ÂÂ¿Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ«Ã¦Â¬ÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂ®Ã£ÂÂ¾Ã£ÂÂ¾Ã¥ÂÂ¥Ã£ÂÂÃ£ÂÂ¦Ã¥ÂÂÃ¥Â¾ÂÃ¦Â¼ÂÃ£ÂÂÃ£ÂÂÃ©ÂÂ²Ã£ÂÂ
                    row.put("time", "Ã¢ÂÂ");
                    row.put("code", "Ã¢ÂÂ");
                    row.put("company", "Ã¢ÂÂ");
                    row.put("title", text);
                    row.put("url", a.absUrl("href"));
                    row.put("tag", "Ã¤Â»Â");
                }
                out.add(row);
                collected++;
            }
        }
        return out;
    }

    // ---------------- Ã¦ÂÂÃ©ÂÂ·Ã¦Â ÂªÃ¥ÂÂÃ¨Â£Â(Ã¦Â±ÂºÃ§Â®ÂÃ£ÂÂ»Ã¥Â¥Â½Ã¦ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ¼Ã£ÂÂ¹) ----------------

    /**
     * Ã¦ÂÂ¢Ã¥Â­ÂÃ£ÂÂ®Ã¤Â¸Â»Ã¥ÂÂÃ£ÂÂ¦Ã£ÂÂ©Ã£ÂÂÃ£ÂÂÃ£ÂÂªÃ£ÂÂ¹Ã£ÂÂÃ£ÂÂ¯Ã¥ÂÂ¤Ã¤Â½ÂÃ§Â½Â®Ã£ÂÂÃ©Â«ÂÃ£ÂÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂ¥Ã¦ÂÂ Ã£ÂÂ§Ã£ÂÂÃ¦Â±ÂºÃ§Â®ÂÃ£ÂÂ»Ã¥Â¥Â½Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ«Ã¥ÂÂºÃ£ÂÂ¥Ã£ÂÂÃ¦ÂÂÃ©ÂÂ·Ã¦Â ÂªÃ¥ÂÂÃ¨Â£ÂÃ£ÂÂÃ£ÂÂ
     * Ã¦Â©ÂÃ¦Â¢Â°Ã§ÂÂÃ£ÂÂ«Ã¦ÂÂ½Ã¥ÂÂºÃ£ÂÂÃ£ÂÂÃ£ÂÂ
     *
     * Ã¥ÂÂ¤Ã¥Â®ÂÃ¦ÂÂ¹Ã¦Â³Â: TDnetÃ£ÂÂ®Ã£ÂÂÃ¦Â¥Â­Ã§Â¸Â¾Ã¤ÂºÂÃ¦ÂÂ³Ã£ÂÂ®Ã¤Â¿Â®Ã¦Â­Â£Ã£ÂÂÃ©ÂÂÃ§Â¤Âº(Ã¦Â ÂªÃ¦ÂÂ¢Ã£ÂÂ® category_group=mod_forecast Ã¤Â¸ÂÃ¨Â¦Â§)Ã£ÂÂ®
     * Ã£ÂÂ¿Ã£ÂÂ¤Ã£ÂÂÃ£ÂÂ«Ã¦ÂÂÃ¨Â¨ÂÃ£ÂÂ«Ã£ÂÂÃ¤Â¸ÂÃ¦ÂÂ¹Ã¤Â¿Â®Ã¦Â­Â£Ã£ÂÂ»Ã¥Â¢ÂÃ©ÂÂÃ£ÂÂªÃ£ÂÂ©Ã¦ÂÂÃ§Â¢ÂºÃ£ÂÂªÃ¥Â¥Â½Ã¦ÂÂÃ¦ÂÂÃ£ÂÂ­Ã£ÂÂ¼Ã£ÂÂ¯Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ¥ÂÂ«Ã£ÂÂ¾Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¤Ã¤Â¸ÂÃ¦ÂÂ¹Ã¤Â¿Â®Ã¦Â­Â£Ã£ÂÂ»Ã§ÂÂ¹Ã¥ÂÂ¥Ã¦ÂÂÃ¥Â¤Â±
     * Ã£ÂÂªÃ£ÂÂ©Ã£ÂÂ®Ã¦ÂÂªÃ¦ÂÂÃ¦ÂÂÃ£ÂÂ­Ã£ÂÂ¼Ã£ÂÂ¯Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ¥ÂÂ«Ã£ÂÂ¾Ã£ÂÂªÃ£ÂÂÃ©ÂÂÃ§Â¤ÂºÃ£ÂÂ Ã£ÂÂÃ£ÂÂÃ¦ÂÂ¡Ã§ÂÂ¨Ã£ÂÂÃ£ÂÂÃ£ÂÂ
     * Ã£ÂÂÃ¦Â±ÂºÃ§Â®ÂÃ£ÂÂÃ¨ÂÂ¯Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ¥Â¥Â½Ã¦ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ¨Ã£ÂÂÃ£ÂÂÃ¥ÂÂ¤Ã¦ÂÂ­Ã£ÂÂÃ£ÂÂ®Ã£ÂÂÃ£ÂÂ®Ã£ÂÂLLMÃ£ÂÂÃ¤Â¸Â»Ã¨Â¦Â³Ã£ÂÂ«Ã©Â Â¼Ã£ÂÂÃ£ÂÂÃ£ÂÂ
     * Ã¤Â¼ÂÃ§Â¤Â¾Ã£ÂÂÃ¥Â®ÂÃ©ÂÂÃ£ÂÂ«TDnetÃ£ÂÂ¸Ã©ÂÂÃ§Â¤ÂºÃ£ÂÂÃ£ÂÂÃ¦ÂÂÃ¨Â¨ÂÃ£ÂÂ®Ã£ÂÂ­Ã£ÂÂ¼Ã£ÂÂ¯Ã£ÂÂ¼Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ®Ã£ÂÂ¿Ã£ÂÂ§Ã¦Â©ÂÃ¦Â¢Â°Ã§ÂÂÃ£ÂÂ»Ã¦Â±ÂºÃ¥Â®ÂÃ¨Â«ÂÃ§ÂÂÃ£ÂÂ«Ã¥ÂÂ¤Ã¥Â®ÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ
     * Ã¦Â¯ÂÃ¥ÂÂÃ£ÂÂ®Ã¨ÂÂªÃ¥ÂÂÃ¥Â®ÂÃ¨Â¡ÂÃ£ÂÂ§Ã£ÂÂÃ¥ÂÂÃ§ÂÂ¾Ã¦ÂÂ§Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ¥ÂÂÃ¥ÂÂÃ¨Â£ÂÃ£ÂÂ«Ã£ÂÂ¯Ã¥Â®ÂÃ©ÂÂÃ£ÂÂ®Ã©ÂÂÃ§Â¤ÂºPDFÃ£ÂÂ¸Ã£ÂÂ®Ã§ÂÂ´Ã£ÂÂªÃ£ÂÂ³Ã£ÂÂ¯Ã£ÂÂÃ¥Â¿ÂÃ£ÂÂÃ¦Â·Â»Ã¤Â»ÂÃ£ÂÂÃ£ÂÂ
     * Ã¦Â Â¹Ã¦ÂÂ Ã£ÂÂÃ©ÂÂÃ§Â¤ÂºÃ¥ÂÂÃ¦ÂÂÃ£ÂÂ§Ã§Â¢ÂºÃ¨ÂªÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ«Ã£ÂÂÃ£ÂÂÃ£ÂÂ
     */
    private static ArrayNode scrapeGrowthCandidates(int maxPages, int maxResults) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)Ã£ÂÂ(.*?)\\s*(Ã¦Â¥Â­Ã¤Â¿Â®)?\\s*(Ã¤Â»ÂÃ¦ÂÂ¥|Ã¦ÂÂÃ¦ÂÂ¥|\\d{1,2}/\\d{1,2}|\\d{1,2}Ã¦ÂÂ\\d{1,2}Ã¦ÂÂ¥\\([Ã¦ÂÂÃ§ÂÂ«Ã¦Â°Â´Ã¦ÂÂ¨Ã©ÂÂÃ¥ÂÂÃ¦ÂÂ¥]\\))\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
        );
        String[] positiveKeywords = {"Ã¤Â¸ÂÃ¦ÂÂ¹Ã¤Â¿Â®Ã¦Â­Â£", "Ã¥Â¢ÂÃ©ÂÂ", "Ã§ÂÂ¹Ã¥ÂÂ¥Ã©ÂÂÃ¥Â½Â", "Ã¥Â¾Â©Ã©ÂÂ", "Ã¥Â¢ÂÃ©Â¡Â"};
        String[] negativeKeywords = {"Ã¤Â¸ÂÃ¦ÂÂ¹Ã¤Â¿Â®Ã¦Â­Â£", "Ã¦Â¸ÂÃ©ÂÂ", "Ã¦Â¸ÂÃ©Â¡Â", "Ã§ÂÂ¡Ã©ÂÂ", "Ã§ÂÂ¹Ã¥ÂÂ¥Ã¦ÂÂÃ¥Â¤Â±"};

        java.util.Set<String> seenCompanies = new java.util.LinkedHashSet<>();
        for (int page = 1; page <= maxPages && out.size() < maxResults; page++) {
            String url = "https://s.kabutan.jp/disclosures/?category_group=mod_forecast" + (page == 1 ? "" : "&page=" + page);
            Document doc;
            try {
                doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
            } catch (Exception e) {
                System.err.println("[WARN] kabutan mod_forecast page " + page + " fetch failed: " + e);
                break;
            }
            List<Element> links = doc.select("a[href^=https://tdnet-pdf.kabutan.jp/]");
            if (links.isEmpty()) break;
            for (Element a : links) {
                if (out.size() >= maxResults) break;
                String text = a.text().trim();

                boolean hasNegative = false;
                for (String neg : negativeKeywords) {
                    if (text.contains(neg)) { hasNegative = true; break; }
                }
                if (hasNegative) continue;

                String matchedKeyword = null;
                for (String pos : positiveKeywords) {
                    if (text.contains(pos)) { matchedKeyword = pos; break; }
                }
                if (matchedKeyword == null) continue;

                Matcher m = rowPattern.matcher(text);
                if (!m.matches()) continue; // Ã¤Â¼ÂÃ§Â¤Â¾Ã¥ÂÂÃ£ÂÂÃ§ÂÂ¹Ã¥Â®ÂÃ£ÂÂ§Ã£ÂÂÃ£ÂÂªÃ£ÂÂÃ¨Â¡ÂÃ£ÂÂ¯Ã¦Â Â¹Ã¦ÂÂ Ã¤Â¸ÂÃ¦ÂÂÃ£ÂÂ¨Ã£ÂÂÃ£ÂÂ¦Ã©ÂÂ¤Ã¥Â¤Â

                String company = m.group(1).trim();
                String title = m.group(2).trim();
                String date = m.group(4);
                String time = m.group(5);
                if (company.isEmpty() || company.equals("Ã¢ÂÂ") || seenCompanies.contains(company)) continue;
                seenCompanies.add(company);

                ObjectNode row = MAPPER.createObjectNode();
                row.put("company", company);
                row.put("title", title);
                row.put("catalyst", matchedKeyword);
                row.put("reason", "TDnetÃ©ÂÂ©Ã¦ÂÂÃ©ÂÂÃ§Â¤ÂºÃ£ÂÂ" + title + "Ã£ÂÂÃ£ÂÂÃ£ÂÂÃ£ÂÂ" + matchedKeyword + "Ã£ÂÂÃ§Â¢ÂºÃ¨ÂªÂÃ£ÂÂ");
                row.put("asof", date + " " + time);
                row.put("url", a.absUrl("href"));
                // Java側鮮度フィルター: 古いアイテムを除外
                java.time.LocalDate todayJst = java.time.LocalDate.now(java.time.ZoneId.of("Asia/Tokyo"));
                java.time.LocalDate cutoff = freshnessCutoff(todayJst);
                java.time.LocalDate itemDate = parseItemDate(date + " " + time, todayJst);
                if (itemDate != null && itemDate.isBefore(cutoff)) {
                    System.out.println("[INFO] Growth filtered (stale): " + company + " asof=" + date);
                    seenCompanies.remove(company); // 除外したので再登録可能にしない
                    continue;
                }
                out.add(row);
            }
        }
        return out;
    }

    // ---------------- Ã¥ÂÂÃ¥ÂÂ¥Ã©ÂÂÃ¦ÂÂÃ£ÂÂÃ£ÂÂ¯Ã£ÂÂÃ£ÂÂ«Ã£ÂÂ«Ã¥ÂÂÃ¦ÂÂ ----------------

    private static ObjectNode scrapeTechnical(String code, String name) throws Exception {
        String url = "https://nikkeiyosoku.com/stock/technical/" + code + "/";
        Document doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
        String text = doc.body().text();

        String price = "Ã¢ÂÂ";
        Double changePct = null;
        Matcher pm = Pattern.compile(
            "Ã§ÂµÂÃ¥ÂÂ¤[Ã¯Â¼Â\\)]\\s*([\\d,]+\\.?\\d*)\\s*([+-][\\d,]+\\.?\\d*)\\(([+-][\\d.]+)%\\)"
        ).matcher(text);
        if (pm.find()) {
            price = pm.group(1);
            changePct = Double.valueOf(pm.group(3));
        }

        String ma5 = extractPct(text, "5Ã¦ÂÂ¥Ã§Â·Â");
        String ma25 = extractPct(text, "25Ã¦ÂÂ¥Ã§Â·Â");
        Double rsi = extractNumber(text, "RSI");

        int sell = 0, neutral = 0, buy = 0;
        Matcher sm = Pattern.compile("Ã¥Â£Â²Ã£ÂÂ\\s*(\\d+)\\s*Ã¤Â¸Â­Ã§Â«Â\\s*(\\d+)\\s*Ã¨Â²Â·Ã£ÂÂ\\s*(\\d+)").matcher(text);
        if (sm.find()) {
            sell = Integer.parseInt(sm.group(1));
            neutral = Integer.parseInt(sm.group(2));
            buy = Integer.parseInt(sm.group(3));
        }

        int diff = buy - sell;
        String base;
        if (diff >= 2) base = "Ã¥Â¼Â·Ã¦Â°Â";
        else if (diff <= -2) base = "Ã¥Â¼Â±Ã¦Â°Â";
        else if (diff == 0) base = "Ã¤Â¸Â­Ã§Â«Â";
        else base = diff > 0 ? "Ã¤Â¸Â­Ã§Â«Â(Ã£ÂÂÃ£ÂÂÃ¥Â¼Â·Ã¦Â°Â)" : "Ã¤Â¸Â­Ã§Â«Â(Ã£ÂÂÃ£ÂÂÃ¥Â¼Â±Ã¦Â°Â)";

        String signal = base;
        if (!base.contains("(")) {
            if (rsi != null && rsi >= 70) signal = base + "(Ã©ÂÂÃ§ÂÂ±Ã¦ÂÂ)";
            else if (rsi != null && rsi <= 30) signal = base + "(Ã¥Â£Â²Ã£ÂÂÃ£ÂÂÃ©ÂÂÃ£ÂÂ)";
            else if (Math.abs(parsePctOrZero(ma25)) >= 10.0) signal = base + "(Ã¤Â¹ÂÃ©ÂÂ¢Ã¥Â¤Â§)";
        }

        StringBuilder summary = new StringBuilder();
        summary.append("Ã¥Â£Â²Ã£ÂÂ").append(sell).append("/Ã¤Â¸Â­Ã§Â«Â").append(neutral).append("/Ã¨Â²Â·Ã£ÂÂ").append(buy).append("Ã£ÂÂ");
        if (rsi != null) {
            if (rsi >= 70) summary.append("RSIÃ£ÂÂ70Ã¨Â¶ÂÃ£ÂÂ§Ã©ÂÂÃ§ÂÂ±Ã¦ÂÂÃ£ÂÂÃ§ÂÂ­Ã¦ÂÂÃ§ÂÂÃ£ÂÂªÃ¥ÂÂÃ¨ÂÂ½Ã£ÂÂªÃ£ÂÂ¹Ã£ÂÂ¯Ã£ÂÂ«Ã§ÂÂÃ¦ÂÂÃ£ÂÂ");
            else if (rsi <= 30) summary.append("RSIÃ£ÂÂ30Ã¤Â»Â¥Ã¤Â¸ÂÃ£ÂÂ§Ã¥Â£Â²Ã£ÂÂÃ£ÂÂÃ©ÂÂÃ£ÂÂÃ£ÂÂÃ§ÂÂ­Ã¦ÂÂÃ§ÂÂÃ£ÂÂªÃ¥ÂÂÃ§ÂÂºÃ¤Â½ÂÃ¥ÂÂ°Ã£ÂÂ«Ã§ÂÂÃ¦ÂÂÃ£ÂÂ");
            else summary.append("RSIÃ£ÂÂ¯Ã¤Â¸Â­Ã§Â«ÂÃ¥ÂÂÃ£ÂÂ");
        }

        ObjectNode node = MAPPER.createObjectNode();
        node.put("code", code);
        node.put("name", name);
        node.put("price", price);
        if (changePct != null) node.put("change_pct", changePct); else node.putNull("change_pct");
        node.put("ma5_dev", ma5);
        node.put("ma25_dev", ma25);
        if (rsi != null) node.put("rsi", rsi); else node.putNull("rsi");
        node.put("signal", signal);
        node.put("summary", summary.toString());
        return node;
    }

    private static String extractPct(String text, String label) {
        Matcher m = Pattern.compile(Pattern.quote(label) + "\\s*([+-]?[\\d.]+)%").matcher(text);
        if (m.find()) {
            String v = m.group(1);
            if (!v.startsWith("+") && !v.startsWith("-")) v = "+" + v;
            return v + "%";
        }
        return "Ã¢ÂÂ";
    }

    private static Double extractNumber(String text, String label) {
        Matcher m = Pattern.compile(Pattern.quote(label) + "\\D{0,20}?([\\d.]+)").matcher(text);
        if (m.find()) {
            try {
                return Double.valueOf(m.group(1));
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return null;
    }

    // ---- ウォッチリスト読み込み ----------------

    /** watchlist.json があればそこから読む。なければ default を返す。 */
    private static String[][] loadWatchlist(File dir, String[][] defaultList) {
        File wlFile = new File(dir != null ? dir : new File("."), "watchlist.json");
        if (!wlFile.exists()) {
            System.out.println("[INFO] watchlist.json not found, using default (" + defaultList.length + " stocks)");
            return defaultList;
        }
        try {
            JsonNode json = MAPPER.readTree(wlFile);
            if (!json.isArray()) return defaultList;
            List<String[]> result = new java.util.ArrayList<>();
            for (JsonNode item : json) {
                String code = item.has("code") ? item.get("code").asText() : null;
                String name = item.has("name") ? item.get("name").asText() : code;
                if (code != null && !code.isEmpty()) result.add(new String[]{code, name != null ? name : code});
            }
            if (result.isEmpty()) return defaultList;
            System.out.println("[INFO] Loaded " + result.size() + " stocks from watchlist.json");
            return result.toArray(new String[0][]);
        } catch (Exception e) {
            System.err.println("[WARN] watchlist.json parse failed: " + e);
            return defaultList;
        }
    }

    // ---- 鮮度チェック(Java側 growth_candidates フィルター) ----------------

    // ---------------- 市場全体の信用情報 ----------------

    /**
     * 空売り比率・信用倍率を取得する。
     * データはnikkeiyosoku.comの市場ページからスクレイピング。
     * 失敗時はnullを返す(既存値を保持)
     */
    private static ObjectNode scrapeMarketCredit() {
        try {
            // kabutan.jp の市場全体の空売り比率ページを取得
            String url = "https://s.kabutan.jp/market/";
            Document doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
            String text = doc.body().text();

            // 空売り比率を抽出
            String shortRatio = null;
            Pattern srPattern = Pattern.compile("空売り比率[\\s\\S]{0,20}?([\\d.]+)%");
            Matcher srM = srPattern.matcher(text);
            if (srM.find()) {
                shortRatio = srM.group(1) + "%";
            }

            // 信用倍率を抽出
            String creditRatio = null;
            Pattern crPattern = Pattern.compile("信用倍率[\\s\\S]{0,20}?([\\d.]+)倍");
            Matcher crM = crPattern.matcher(text);
            if (crM.find()) {
                creditRatio = crM.group(1) + "倍";
            }

            if (shortRatio == null && creditRatio == null) return null;

            ObjectNode info = MAPPER.createObjectNode();
            if (shortRatio != null) info.put("short_ratio", shortRatio);
            if (creditRatio != null) info.put("credit_ratio", creditRatio);
            info.put("margin_buy", "");
            info.put("margin_sell", "");
            ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
            info.put("asof", nowJst.format(DateTimeFormatter.ofPattern("M/d")));
            return info;
        } catch (Exception e) {
            System.err.println("[WARN] market credit scrape failed: " + e);
            return null;
        }
    }

    private static java.time.LocalDate freshnessCutoff(java.time.LocalDate today) {
        int dow = today.getDayOfWeek().getValue(); // 1=Mon … 6=Sat, 7=Sun
        if (dow == 1) return today.minusDays(2);      // 月曜: 土まで遡る
        else if (dow == 6) return today.minusDays(1); // 土曜: 金まで遡る
        else if (dow == 7) return today.minusDays(1); // 日曜: 土まで遡る
        else return today;                             // 火〜金: 当日のみ
    }

    private static java.time.LocalDate parseItemDate(String dateStr, java.time.LocalDate today) {
        if (dateStr == null || dateStr.isEmpty()) return null;
        if (dateStr.startsWith("今日")) return today;
        if (dateStr.startsWith("昨日")) return today.minusDays(1);
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("(\\d{1,2})/(\\d{1,2})").matcher(dateStr);
        if (m.find()) {
            try { return java.time.LocalDate.of(today.getYear(), Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2))); } catch (Exception ignored) {}
        }
        m = java.util.regex.Pattern.compile("(\\d{1,2})\\u6708(\\d{1,2})\\u65e5").matcher(dateStr);
        if (m.find()) {
            try { return java.time.LocalDate.of(today.getYear(), Integer.parseInt(m.group(1)), Integer.parseInt(m.group(2))); } catch (Exception ignored) {}
        }
        return null;
    }

    private static double parsePctOrZero(String pct) {
        if (pct == null) return 0.0;
        try {
            return Double.parseDouble(pct.replace("%", "").replace("+", ""));
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }
}
