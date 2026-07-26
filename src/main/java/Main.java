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
 * æ¥æ¬æ ª(æ±è¨¼)ãã¤ãã¬ã¼ãããã·ã¥ãã¼ãç¨ãã¼ã¿æ´æ°ãã¼ã«ã
 *
 * ãã®ãã­ã°ã©ã ã ãã§ data.json ããæ±ºå®è«çã«ãæ´æ°ãã(WebSearchç­ã§LLMã
 * æåã§æå ±åéããä»£ããã«ãç¡æã»ã­ã¼ä¸è¦ã®å¬éã½ã¼ã¹ãç´æ¥HTTPã§åå¾ãã)ã
 * HTMLçæã¯æ¢å­ã® render_dashboard.py ã«ãã®ã¾ã¾ä»»ãã(ãããã¯ã¼ã¯ä¸è¦ã®Pure Python)ã
 *
 * ä½¿ãæ¹: java -jar dashboard-updater.jar <morning|evening> <data.jsonã®ãã¹>
 */
public class Main {

    private static final String UA =
        "Mozilla/5.0 (compatible; jp-daytrade-dashboard-bot/1.0; " +
        "+https://github.com/tkynakanaka0506-ux/jp-daytrade-dashboard)";

    private static final HttpClient HTTP = HttpClient.newBuilder()
        .connectTimeout(Duration.ofSeconds(15))
        .build();

    private static final ObjectMapper MAPPER = new ObjectMapper();

    // å®ç¹è¦³æ¸¬ããåå¥éæãå¢æ¸ãããå ´åã¯ãããç·¨éããã ãã§ããã
    private static final String[][] WATCHLIST = {
        {"7203", "ãã¨ã¿èªåè»"},
        {"6758", "ã½ãã¼ã°ã«ã¼ã"},
        {"8306", "ä¸è±UFJãã£ãã³ã·ã£ã«ã»ã°ã«ã¼ã"},
        {"9984", "ã½ãããã³ã¯ã°ã«ã¼ã"},
    };

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "morning"; // "morning" or "evening"
        File dataFile = new File(args.length > 1 ? args[1] : "data.json");

        ObjectNode root = (ObjectNode) MAPPER.readTree(dataFile);

        ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
        root.put("generated_at", nowJst.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")));
        root.put("run_type", mode);

        // ---- å¸å ´ææ¨(ç¡æã»ã­ã¼ä¸è¦ã®Yahoo Finance chart APIããåå¾) ----
        updateNested(root, "us_market", "sp500", "^GSPC", false);
        updateNested(root, "us_market", "dow", "^DJI", false);
        updateNested(root, "us_market", "nasdaq", "^IXIC", false);
        updateNested(root, "us_market", "sox", "^SOX", false);
        updateTopLevel(root, "fx", "JPY=X", true);
        updateTopLevel(root, "nikkei225", "^N225", false);
        updateTopLevel(root, "nikkei_futures", "NIY=F", false); // ãã¹ãã¨ãã©ã¼ããåããªããã°æ¢å­å¤ãä¿æ

        // ---- TDneté©æéç¤º(æ ªæ¢ã¢ãã¤ã«çãã©ã¼ãã¹ã¯ã¬ã¤ãã³ã°) ----
        try {
            ArrayNode disclosures = scrapeKabutanDisclosures(3);
            if (disclosures.size() > 0) {
                root.set("evening".equals(mode) ? "tdnet_afterclose" : "tdnet_morning", disclosures);
            }
        } catch (Exception e) {
            System.err.println("[WARN] kabutan disclosures fetch failed: " + e);
        }

        // ---- åå¥éæãã¯ãã«ã«åæ(æè³ã®æ£®ãã¹ã¯ã¬ã¤ãã³ã°) ----
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

        // ---- æé·æ ªåè£(TDnetãæ¥­ç¸¾äºæ³ã®ä¿®æ­£ãéç¤ºã®ãã¡å¥½ææã®ã¿ãæ©æ¢°çã«æ½åº) ----
        try {
            ArrayNode growth = scrapeGrowthCandidates(8, 8);
            if (growth.size() > 0) {
                root.set("growth_candidates", growth);
            }
        } catch (Exception e) {
            System.err.println("[WARN] growth candidates fetch failed: " + e);
        }

        // æ³¨: overnight_news / afterclose_news / movers_morning / movers_afterclose ã¯
        // ãè©±é¡æ§ã®ãããã¥ã¼ã¹ã»éæããé¸ã¶æ§è³ªä¸ãç¡æã®æ±ºå®è«çAPIã ãã§ã¯åç¾ã§ããªããã
        // ãã®Javaçã§ã¯æ´æ°å¯¾è±¡å¤(æ¢å­ã®å¤ããã®ã¾ã¾ä¿æãã)ã
        // ãã¥ã¼ã¹APIç­ãå°å¥ããå ´åã¯ãã­ã¼ãGitHub Secretsã«ç»é²ãããã§èª­ã¿è¾¼ãå½¢ã«æ¡å¼µããã

        MAPPER.writerWithDefaultPrettyPrinter().writeValue(dataFile, root);
        System.out.println("[OK] data.json updated (mode=" + mode + ")");
    }

    // ---------------- å¸å ´ææ¨ ----------------

    /** us_market.sp500 ã®ãããª1éå±¤ãã¹ããããªãã¸ã§ã¯ããæ´æ°ãã */
    private static void updateNested(ObjectNode root, String parentField, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // å¤±ææã¯æ¢å­å¤ãä¿æ
        ObjectNode parent = root.has(parentField) && root.get(parentField).isObject()
            ? (ObjectNode) root.get(parentField)
            : MAPPER.createObjectNode();
        parent.set(field, target);
        root.set(parentField, parent);
    }

    /** fx / nikkei225 / nikkei_futures ã®ãããªãããã¬ãã«ç´ä¸ã®ãã£ã¼ã«ããæ´æ°ãã */
    private static void updateTopLevel(ObjectNode root, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return; // å¤±ææã¯æ¢å­å¤ãä¿æ
        root.set(field, target);
    }

    private static boolean fillQuote(ObjectNode target, String symbol, boolean isFx) {
        try {
            // "^"ã¯RFC3986ä¸ãã¹ä¸­ã®åæ³æå­ã§ã¯ãªãURI.create()ãä¾å¤ãæããããã
            // ^GSPC/^DJI/^IXIC/^N225ç­ã®ã¤ã³ããã¯ã¹ã·ã³ãã«ã¯äºåã«ãã¼ã»ã³ãã¨ã³ã³ã¼ãããã
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

            // æ³¨: meta.chartPreviousCloseã¯ãrangeå¼æ°(ããã§ã¯5d)ã®ãã£ã¼ãéå§æ¥ããåã®çµå¤ãã§ããã
            // ç´è¿ã®å¶æ¥­æ¥ã®çµå¤ã¨ã¯ç°ãªã(ä¾: é±æ«ãæãã¨1é±éè¿ãåã®å¤ã«ãªãå¾ã)ã
            // ã¾ãå®éã«ã¯meta.previousCloseãã£ã¼ã«ãèªä½ããã®APIã®ã¬ã¹ãã³ã¹ã«å«ã¾ããªããã¨ãå¤ãã
            // ãããåªåæ¡ä»¶ã«ãã¦ãå®è³ªçã«chartPreviousCloseã¸ãã©ã¼ã«ããã¯ãç¶ãã¦ãã¾ãã
            // ããã§ãåå¶æ¥­æ¥æ¯ãã«ã¯ãæ¥æ¬¡ã­ã¼ã½ã¯è¶³éå(indicators.quote[0].close)ã®
            // ãç´è¿ãã2çªç®ã®çµå¤ããä½¿ããéåã®æå¾ã®è¦ç´ ã¯ç´è¿ã®åå¼æ¥(=regularMarketPriceã®æ¥)ã®
            // çµå¤(åå¼æéä¸­ã¯æªç¢ºå®ã§nullã®å ´åããã)ããã®1ã¤åãæ­£ãããåå¶æ¥­æ¥ã®çµå¤ãã«ãªãã
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
            // ä¸ä¸æ¥æ¬¡çµå¤éåãåå¾ã§ããªãå ´åã®ã¿ãå¾æ¥ã®chartPreviousCloseã«ãã©ã¼ã«ããã¯ãã
            // (ç²¾åº¦ã¯è½ã¡ãããå¤ãä¸¸ãã¨è«¦ããããã¯è¯ã)ã
            if (Double.isNaN(prevClose)) prevClose = meta.path("chartPreviousClose").asDouble(Double.NaN);
            if (Double.isNaN(price) || Double.isNaN(prevClose) || prevClose == 0) return false;

            double changePct = (price - prevClose) / prevClose * 100.0;

            DecimalFormat df = new DecimalFormat("#,##0.00", new DecimalFormatSymbols(Locale.US));
            String valueStr = df.format(price) + (isFx ? "å" : "");

            String marketState = meta.path("marketState").asText("CLOSED");
            String stateLabel = switch (marketState) {
                case "REGULAR" -> "ç¾å¨å¤";
                case "PRE" -> "ãã¬ãã¼ã±ãã";
                case "POST" -> "ã¢ãã¿ã¼ãã¼ã±ãã";
                default -> "çµå¤";
            };
            // æ³¨: æ¥ä»ã©ãã«ã«ã¯ãåå¾ããä»ãã®ç¬éãã§ã¯ãªããå®éã«ãã®å¤ãè¦³æ¸¬ãããæå»
            // (meta.regularMarketTimeãåå¼ä¸­ã®ææ¨ã¯ãã®æç¹ãåå¼çµäºå¾ã®ææ¨ã¯ç´è¿çµå¤ã®æå»)ãä½¿ãã
            // åæ¥ãç¥æ¥ã«ã¸ã§ããèµ°ããã¦ããå®éã®æçµåå¼æ¥ã®æ¥ä»ãæ­£ããè¡¨ç¤ºãããããã«ããããã
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

    // ---------------- TDneté©æéç¤º ----------------

    private static ArrayNode scrapeKabutanDisclosures(int maxPages) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)ã(.*?)\\s*(æ±ºç®|éå½|æ¥­ä¿®|èªç¤¾|ã¨ã¯|è¿½è¨|ä»)?\\s*(ä»æ¥|ææ¥|\\d{1,2}/\\d{1,2})\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
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
            // éç¤ºPDFã¸ã®ç´ãªã³ã¯ã ããå¯¾è±¡ã«ãã(ããã²ã¼ã·ã§ã³ç­ã®ãã¤ãºãèªç¶ã«é¤å¤ã§ãã)
            List<Element> links = doc.select("a[href^=https://tdnet-pdf.kabutan.jp/]");
            if (links.isEmpty()) break;
            for (Element a : links) {
                if (collected >= 20) break;
                String text = a.text().trim();
                Matcher m = rowPattern.matcher(text);
                ObjectNode row = MAPPER.createObjectNode();
                if (m.matches()) {
                    row.put("time", m.group(5));
                    row.put("code", "â");
                    row.put("company", m.group(1).trim());
                    row.put("title", m.group(2).trim());
                    row.put("url", a.absUrl("href"));
                    row.put("tag", m.group(3) != null ? m.group(3) : "ä»");
                } else {
                    // æ³å®å¤ã®ãã©ã¼ãããã®è¡ã¯ã¿ã¤ãã«æ¬ã«ãã®ã¾ã¾å¥ãã¦åå¾æ¼ããé²ã
                    row.put("time", "â");
                    row.put("code", "â");
                    row.put("company", "â");
                    row.put("title", text);
                    row.put("url", a.absUrl("href"));
                    row.put("tag", "ä»");
                }
                out.add(row);
                collected++;
            }
        }
        return out;
    }

    // ---------------- æé·æ ªåè£(æ±ºç®ã»å¥½ææãã¼ã¹) ----------------

    /**
     * æ¢å­ã®ä¸»åã¦ã©ãããªã¹ãã¯å¤ä½ç½®ãé«ãã®ãããå¥æ ã§ãæ±ºç®ã»å¥½ææã«åºã¥ãæé·æ ªåè£ãã
     * æ©æ¢°çã«æ½åºããã
     *
     * å¤å®æ¹æ³: TDnetã®ãæ¥­ç¸¾äºæ³ã®ä¿®æ­£ãéç¤º(æ ªæ¢ã® category_group=mod_forecast ä¸è¦§)ã®
     * ã¿ã¤ãã«æè¨ã«ãä¸æ¹ä¿®æ­£ã»å¢éãªã©æç¢ºãªå¥½ææã­ã¼ã¯ã¼ããå«ã¾ãããã¤ä¸æ¹ä¿®æ­£ã»ç¹å¥æå¤±
     * ãªã©ã®æªææã­ã¼ã¯ã¼ããå«ã¾ãªãéç¤ºã ããæ¡ç¨ããã
     * ãæ±ºç®ãè¯ãããå¥½ææããããã¨ããå¤æ­ãã®ãã®ãLLMãä¸»è¦³ã«é ¼ããã
     * ä¼ç¤¾ãå®éã«TDnetã¸éç¤ºããæè¨ã®ã­ã¼ã¯ã¼ããããã®ã¿ã§æ©æ¢°çã»æ±ºå®è«çã«å¤å®ããããã
     * æ¯åã®èªåå®è¡ã§ãåç¾æ§ããããååè£ã«ã¯å®éã®éç¤ºPDFã¸ã®ç´ãªã³ã¯ãå¿ãæ·»ä»ãã
     * æ ¹æ ãéç¤ºåæã§ç¢ºèªã§ããããã«ããã
     */
    private static ArrayNode scrapeGrowthCandidates(int maxPages, int maxResults) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)ã(.*?)\\s*(æ¥­ä¿®)?\\s*(ä»æ¥|ææ¥|\\d{1,2}/\\d{1,2}|\\d{1,2}æ\\d{1,2}æ¥\\([æç«æ°´æ¨éåæ¥]\\))\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
        );
        String[] positiveKeywords = {"ä¸æ¹ä¿®æ­£", "å¢é", "ç¹å¥éå½", "å¾©é", "å¢é¡"};
        String[] negativeKeywords = {"ä¸æ¹ä¿®æ­£", "æ¸é", "æ¸é¡", "ç¡é", "ç¹å¥æå¤±"};

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
                if (!m.matches()) continue; // ä¼ç¤¾åãç¹å®ã§ããªãè¡ã¯æ ¹æ ä¸æã¨ãã¦é¤å¤

                String company = m.group(1).trim();
                String title = m.group(2).trim();
                String date = m.group(4);
                String time = m.group(5);
                if (company.isEmpty() || company.equals("â") || seenCompanies.contains(company)) continue;
                seenCompanies.add(company);

                ObjectNode row = MAPPER.createObjectNode();
                row.put("company", company);
                row.put("title", title);
                row.put("catalyst", matchedKeyword);
                row.put("reason", "TDneté©æéç¤ºã" + title + "ãããã" + matchedKeyword + "ãç¢ºèªã");
                row.put("asof", date + " " + time);
                row.put("url", a.absUrl("href"));
                out.add(row);
            }
        }
        return out;
    }

    // ---------------- åå¥éæãã¯ãã«ã«åæ ----------------

    private static ObjectNode scrapeTechnical(String code, String name) throws Exception {
        String url = "https://nikkeiyosoku.com/stock/technical/" + code + "/";
        Document doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
        String text = doc.body().text();

        String price = "â";
        Double changePct = null;
        Matcher pm = Pattern.compile(
            "çµå¤[ï¼\\)]\\s*([\\d,]+\\.?\\d*)\\s*([+-][\\d,]+\\.?\\d*)\\(([+-][\\d.]+)%\\)"
        ).matcher(text);
        if (pm.find()) {
            price = pm.group(1);
            changePct = Double.valueOf(pm.group(3));
        }

        String ma5 = extractPct(text, "5æ¥ç·");
        String ma25 = extractPct(text, "25æ¥ç·");
        Double rsi = extractNumber(text, "RSI");

        int sell = 0, neutral = 0, buy = 0;
        Matcher sm = Pattern.compile("å£²ã\\s*(\\d+)\\s*ä¸­ç«\\s*(\\d+)\\s*è²·ã\\s*(\\d+)").matcher(text);
        if (sm.find()) {
            sell = Integer.parseInt(sm.group(1));
            neutral = Integer.parseInt(sm.group(2));
            buy = Integer.parseInt(sm.group(3));
        }

        int diff = buy - sell;
        String base;
        if (diff >= 2) base = "å¼·æ°";
        else if (diff <= -2) base = "å¼±æ°";
        else if (diff == 0) base = "ä¸­ç«";
        else base = diff > 0 ? "ä¸­ç«(ããå¼·æ°)" : "ä¸­ç«(ããå¼±æ°)";

        String signal = base;
        if (!base.contains("(")) {
            if (rsi != null && rsi >= 70) signal = base + "(éç±æ)";
            else if (rsi != null && rsi <= 30) signal = base + "(å£²ããéã)";
            else if (Math.abs(parsePctOrZero(ma25)) >= 10.0) signal = base + "(ä¹é¢å¤§)";
        }

        StringBuilder summary = new StringBuilder();
        summary.append("å£²ã").append(sell).append("/ä¸­ç«").append(neutral).append("/è²·ã").append(buy).append("ã");
        if (rsi != null) {
            if (rsi >= 70) summary.append("RSIã70è¶ã§éç±æãç­æçãªåè½ãªã¹ã¯ã«çæã");
            else if (rsi <= 30) summary.append("RSIã30ä»¥ä¸ã§å£²ããéããç­æçãªåçºä½å°ã«çæã");
            else summary.append("RSIã¯ä¸­ç«åã");
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
        return "â";
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
