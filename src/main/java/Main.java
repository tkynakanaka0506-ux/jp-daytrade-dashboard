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
 * 日本株(東証)デイトレードダッシュボード用データ更新ツール。
 *
 * このプログラムだけで data.json を「決定論的に」更新する(WebSearch等でLLMが
 * 手動で情報収集する代わりに、無料・キー不要の公開ソースを直接HTTPで取得する)。
 * HTML生成は既存の render_dashboard.py にそのまま任せる(ネットワーク不要のPure Python)。
 *
 * 使い方: java -jar dashboard-updater.jar <morning|evening> <data.jsonのパス>
 */
public class Main {

    private static final String UA =
        "Mozilla/5.0 (compatible; jp-daytrade-dashboard-bot/1.0; " +
        "+https://github.com/tkynakanaka0506-ux/jp-daytrade-dashboard)";

    private static final HttpClient HTTP = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(15))
        .build();

    private static final ObjectMapper MAPPER = new ObjectMapper();

    // 定点観測する個別銘柄。増減したい場合はここを編集するだけでよい。
    private static final String[][] WATCHLIST = {
        {"7203", "トヨタ自動車"},
        {"6758", "ソニーグループ"},
        {"8306", "三菱UFJフィナンシャル・グループ"},
        {"9984", "ソフトバンクグループ"},
    };

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "morning"; // "morning" or "evening"
        File dataFile = new File(args.length > 1 ? args[1] : "data.json");

        ObjectNode root = (ObjectNode) MAPPER.readTree(dataFile);

        ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
        root.put("generated_at", nowJst.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        root.put("run_type", mode);

        // ---- 市場指標(無料・キー不要のYahoo Finance chart APIから取得) ----
        updateNested(root, "us_market", "sp500", "^GSPC", false);
        updateNested(root, "us_market", "dow", "^DJI", false);
        updateNested(root, "us_market", "nasdaq", "^IXIC", false);
        updateTopLevel(root, "fx", "JPY=X", true);
        updateTopLevel(root, "nikkei225", "^N225", false);
        updateTopLevel(root, "nikkei_futures", "NIY=F", false); // ベストエフォート。取れなければ既存値を保持

        // ---- TDnet適時開示(株探モバイル版ミラーをスクレイピング) ----
        try {
            ArrayNode disclosures = scrapeKabutanDisclosures(3);
            if (disclosures.size() > 0) {
                root.set("evening".equals(mode) ? "tdnet_afterclose" : "tdnet_morning", disclosures);
            }
        } catch (Exception e) {
            System.err.println("[WARN] kabutan disclosures fetch failed: " + e);
        }

        // ---- 個別銘柄テクニカル分析(投資の森をスクレイピング) ----
        ArrayNode technical = MAPPER.createArrayNode();
        for (String[] w : WATCHLIST) {
            try {
                technical.add(scrapeTechnical(w[0], w[1]));
            } catch (Exception e) {
                System.err.println("[WARN] technical fetch failed for " + w[0] + ": " + e);
            }
        }
        if (technical.size() > 0) {
            root.set("technical", technical);
        }

        // 注: overnight_news / afterclose_news / movers_morning / movers_afterclose は
        // 「話題性のあるニュース・銘柄」を選ぶ性質上、無料の決定論的APIだけでは再現できないため
        // このJava版では更新対象外(既存の値をそのまま保持する)。
        // ニュースAPI等を導入する場合は、キーをGitHub Secretsに登録しここで読み込む形に拡張する。

        MAPPER.writerWithDefaultPrettyPrinter().writeValue(dataFile, root);
        System.out.println("[OK] data.json updated (mode=" + mode + ")");
    }

    // ---------------- 市場指標 ----------------

    /** us_market.sp500 のような1階層ネストしたオブジェクトを更新する */
    private static void updateNested(ObjectNode root, String parentField, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // 失敗時は既存値を保持
        ObjectNode parent = root.has(parentField) && root.get(parentField).isObject()
            ? (ObjectNode) root.get(parentField)
            : MAPPER.createObjectNode();
        parent.set(field, target);
        root.set(parentField, parent);
    }

    /** fx / nikkei225 / nikkei_futures のようなトップレベル直下のフィールドを更新する */
    private static void updateTopLevel(ObjectNode root, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // 失敗時は既存値を保持
        root.set(field, target);
    }

    private static boolean fillQuote(ObjectNode target, String symbol, boolean isFx) {
        try {
            // "^"はRFC3986上パス中の合法文字ではなくURI.create()が例外を投げるため、
            // ^GSPC/^DJI/^IXIC/^N225等のインデックスシンボルは事前にパーセントエンコードする。
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
            // 注: chartPreviousCloseはrange引数(ここでは5d)の開始日より前の終値であり、
            // 「前営業日比」には使えない(週末などを挟むと直近の終値と一致しない)。
            // 前営業日比の計算にはmeta.previousCloseを優先し、それが無い場合のみ
            // chartPreviousCloseにフォールバックする。
            double prevClose = meta.path("previousClose").asDouble(Double.NaN);
            if (Double.isNaN(prevClose)) prevClose = meta.path("chartPreviousClose").asDouble(Double.NaN);
            if (Double.isNaN(price) || Double.isNaN(prevClose) || prevClose == 0) return false;

            double changePct = (price - prevClose) / prevClose * 100.0;

            DecimalFormat df = new DecimalFormat("#,##0.00", new DecimalFormatSymbols(Locale.US));
            String valueStr = df.format(price) + (isFx ? "円" : "");

            String marketState = meta.path("marketState").asText("CLOSED");
            String stateLabel = switch (marketState) {
                case "REGULAR" -> "現在値";
                case "PRE" -> "プレマーケット";
                case "POST" -> "アフターマーケット";
                default -> "終値";
            };
            ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
            String asof = nowJst.format(DateTimeFormatter.ofPattern("M/d")) + stateLabel;

            target.put("value", valueStr);
            target.put("change_pct", Math.round(changePct * 100) / 100.0);
            target.put("asof", asof);
            return true;
        } catch (Exception e) {
            System.err.println("[WARN] quote fetch failed for " + symbol + ": " + e);
            return false;
        }
    }

    // ---------------- TDnet適時開示 ----------------

    private static ArrayNode scrapeKabutanDisclosures(int maxPages) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)、(.*?)\\s*(決算|配当|業修|自社|エク|追訂|他)?\\s*(今日|明日|\\d{1,2}/\\d{1,2})\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
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
            // 開示PDFへの直リンクだけを対象にする(ナビゲーション等のノイズを自然に除外できる)
            List<Element> links = doc.select("a[href^=https://tdnet-pdf.kabutan.jp/]");
            if (links.isEmpty()) break;
            for (Element a : links) {
                if (collected >= 20) break;
                String text = a.text().trim();
                Matcher m = rowPattern.matcher(text);
                ObjectNode row = MAPPER.createObjectNode();
                if (m.matches()) {
                    row.put("time", m.group(5));
                    row.put("code", "―");
                    row.put("company", m.group(1).trim());
                    row.put("title", m.group(2).trim());
                    row.put("url", a.absUrl("href"));
                    row.put("tag", m.group(3) != null ? m.group(3) : "他");
                } else {
                    // 想定外のフォーマットの行はタイトル欄にそのまま入れて取得漏れを防ぐ
                    row.put("time", "―");
                    row.put("code", "―");
                    row.put("company", "―");
                    row.put("title", text);
                    row.put("url", a.absUrl("href"));
                    row.put("tag", "他");
                }
                out.add(row);
                collected++;
            }
        }
        return out;
    }

    // ---------------- 個別銘柄テクニカル分析 ----------------

    private static ObjectNode scrapeTechnical(String code, String name) throws Exception {
        String url = "https://nikkeiyosoku.com/stock/technical/" + code + "/";
        Document doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
        String text = doc.body().text();

        String price = "―";
        Double changePct = null;
        Matcher pm = Pattern.compile(
            "終値[）\\)]\\s*([\\d,]+\\.?\\d*)\\s*([+-][\\d,]+\\.?\\d*)\\(([+-][\\d.]+)%\\)"
        ).matcher(text);
        if (pm.find()) {
            price = pm.group(1);
            changePct = Double.valueOf(pm.group(3));
        }

        String ma5 = extractPct(text, "5日線");
        String ma25 = extractPct(text, "25日線");
        Double rsi = extractNumber(text, "RSI");

        int sell = 0, neutral = 0, buy = 0;
        Matcher sm = Pattern.compile("売り\\s*(\\d+)\\s*中立\\s*(\\d+)\\s*買い\\s*(\\d+)").matcher(text);
        if (sm.find()) {
            sell = Integer.parseInt(sm.group(1));
            neutral = Integer.parseInt(sm.group(2));
            buy = Integer.parseInt(sm.group(3));
        }

        int diff = buy - sell;
        String base;
        if (diff >= 2) base = "強気";
        else if (diff <= -2) base = "弱気";
        else if (diff == 0) base = "中立";
        else base = diff > 0 ? "中立(やや強気)" : "中立(やや弱気)";

        String signal = base;
        if (!base.contains("(")) {
            if (rsi != null && rsi >= 70) signal = base + "(過熱感)";
            else if (rsi != null && rsi <= 30) signal = base + "(売られ過ぎ)";
            else if (Math.abs(parsePctOrZero(ma25)) >= 10.0) signal = base + "(乖離大)";
        }

        StringBuilder summary = new StringBuilder();
        summary.append("売り").append(sell).append("/中立").append(neutral).append("/買い").append(buy).append("。");
        if (rsi != null) {
            if (rsi >= 70) summary.append("RSIが70超で過熱感、短期的な反落リスクに留意。");
            else if (rsi <= 30) summary.append("RSIが30以下で売られ過ぎ、短期的な反発余地に留意。");
            else summary.append("RSIは中立域。");
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
        return "―";
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

    private static double parsePctOrZero(String pct) {
        if (pct == null) return 0.0;
        try {
            return Double.parseDouble(pct.replace("%", "").replace("+", ""));
        } catch (NumberFormatException e) {
            return 0.0;
        }
    }
}
