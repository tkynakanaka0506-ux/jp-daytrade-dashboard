import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.jsoup.Jsoup;
import org.jsoup.nodes.Document;
import org.jsoup.nodes.Element;
import org.jsoup.parser.Parser;
import org.jsoup.select.Elements;

import java.io.File;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
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

    // 画面・通知で利用するすべての取得データ。実行開始時に必ず空にし、前回実行の
    // 成功データが今回の失敗時に残らないようにする。
    private static final String[] TRACKED_FIELDS = {
        "market_quotes", "tdnet_morning", "tdnet_afterclose", "technical",
        "growth_candidates", "pre_earnings_watch", "overnight_news", "afterclose_news",
        "movers_morning", "movers_afterclose", "us_good_news", "edinet_large_holdings",
        "economic_calendar"
    };

    // 定点観測する個別銘柄。増減したい場合はここを編集するだけでよい。
    // 2026-08-01: これまでクロード側が手動収集していたテクニカル指標20銘柄と同一構成に拡張。
    private static final String[][] WATCHLIST = {
        {"7203", "トヨタ自動車"},
        {"6758", "ソニーグループ"},
        {"8306", "三菱UFJフィナンシャル・グループ"},
        {"9984", "ソフトバンクグループ"},
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

    // 2026-08-02: 「相場環境の俯瞰(セクター分析)」機能追加のため、東証33業種ベースの
    // 簡易セクター区分を銘柄コードにひも付けたルックアップテーブルを追加。
    // ウォッチリストが20銘柄と少数のため、外部APIから業種を都度取得するのではなく、
    // 無料・キー不要かつ即時に使える固定マップとして保持する(コード変更時は手動更新が必要)。
    private static final java.util.Map<String, String> SECTOR_MAP = new java.util.HashMap<>();
    static {
        SECTOR_MAP.put("7203", "輸送用機器");
        SECTOR_MAP.put("6758", "電気機器");
        SECTOR_MAP.put("8306", "銀行業");
        SECTOR_MAP.put("9984", "情報・通信業");
        SECTOR_MAP.put("6861", "電気機器");
        SECTOR_MAP.put("6954", "機械");
        SECTOR_MAP.put("7974", "その他製品");
        SECTOR_MAP.put("6098", "サービス業");
        SECTOR_MAP.put("8035", "電気機器");
        SECTOR_MAP.put("9433", "情報・通信業");
        SECTOR_MAP.put("9432", "情報・通信業");
        SECTOR_MAP.put("7267", "輸送用機器");
        SECTOR_MAP.put("6367", "機械");
        SECTOR_MAP.put("9983", "小売業");
        SECTOR_MAP.put("4063", "化学");
        SECTOR_MAP.put("6857", "電気機器");
        SECTOR_MAP.put("4519", "医薬品");
        SECTOR_MAP.put("5401", "鉄鋼");
        SECTOR_MAP.put("2413", "サービス業");
        SECTOR_MAP.put("6645", "電気機器");
    }

    public static void main(String[] args) throws Exception {
        String mode = args.length > 0 ? args[0] : "morning"; // "morning" or "evening"
        File dataFile = new File(args.length > 1 ? args[1] : "data.json");

        ObjectNode root = (ObjectNode) MAPPER.readTree(dataFile);

        ZonedDateTime nowJst = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
        String generatedAt = nowJst.format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm"));
        root.put("generated_at", generatedAt);
        root.put("run_type", mode);
        // 毎実行時に前回値を先に消去する。以降の各取得が失敗しても、過去の情報を
        // 当回の情報として表示・通知に流用しないためのフェイルクローズ設計である。
        resetStaleData(root, generatedAt);

        // ---- 市場指標(無料・キー不要のYahoo Finance chart APIから取得) ----
        int marketSuccessCount = 0;
        if (updateNested(root, "us_market", "sp500", "^GSPC", false)) marketSuccessCount++;
        if (updateNested(root, "us_market", "dow", "^DJI", false)) marketSuccessCount++;
        if (updateNested(root, "us_market", "nasdaq", "^IXIC", false)) marketSuccessCount++;
        if (updateNested(root, "us_market", "sox", "^SOX", false)) marketSuccessCount++;
        if (updateTopLevel(root, "fx", "JPY=X", true)) marketSuccessCount++;
        if (updateTopLevel(root, "nikkei225", "^N225", false)) marketSuccessCount++;
        if (updateTopLevel(root, "nikkei_futures", "NIY=F", false)) marketSuccessCount++;
        if (marketSuccessCount == 7) {
            markUpdated(root, "market_quotes", generatedAt);
        } else if (marketSuccessCount > 0) {
            markPartial(root, "market_quotes", generatedAt,
                "7項目中" + marketSuccessCount + "項目を取得。一部は取得不可です。");
        } else {
            markUnavailable(root, "market_quotes", generatedAt, "市場指数・為替を取得できませんでした。");
        }

        // ---- TDnet適時開示(株探モバイル版ミラーをスクレイピング) ----
        String tdnetField = "evening".equals(mode) ? "tdnet_afterclose" : "tdnet_morning";
        String otherTdnetField = "evening".equals(mode) ? "tdnet_morning" : "tdnet_afterclose";
        markNotRequested(root, otherTdnetField, generatedAt, "今回の実行モードでは更新対象外です。");
        try {
            ArrayNode disclosures = scrapeKabutanDisclosures(3);
            root.set(tdnetField, disclosures);
            if (disclosures.size() > 0) {
                markUpdated(root, tdnetField, generatedAt);
            } else {
                markEmpty(root, tdnetField, generatedAt, "取得済み・該当する開示はありません。");
            }
        } catch (Exception e) {
            markUnavailable(root, tdnetField, generatedAt, "TDnet開示を取得できませんでした。");
            System.err.println("[WARN] kabutan disclosures fetch failed: " + e);
        }

        // ---- 個別銘柄テクニカル分析(投資の森をスクレイピング) ----
        // 2026-08-02: 「織り込み済みリスク判定」強化のため、以下を追加(すべて無料・規約遵守の範囲):
        //   ・ret_5d_pct       … 直近5日騰落率(Yahoo Finance chart APIのrange=1y日足から算出。先回り買いの検知用)
        //   ・high_52w_dist_pct… 52週高値からの位置(同API。高値圏で好材料が出た場合の「材料出尽くし」検知用)
        //   ・credit_ratio     … 信用倍率(JPX公式「銘柄別信用取引週末残高」PDFより算出。需給の過熱感の目安)
        //   ・minkabu_url      … みんかぶのアナリストコンセンサスページへの参考リンク(規約上スクレイピングはせず、
        //                         手動確認用のリンクのみを掲載する)
        String[] watchlistCodes = new String[WATCHLIST.length];
        for (int i = 0; i < WATCHLIST.length; i++) watchlistCodes[i] = WATCHLIST[i][0];
        java.util.Map<String, Double> creditRatios = fetchJpxCreditRatios(watchlistCodes);

        ArrayNode technical = MAPPER.createArrayNode();
        for (String[] w : WATCHLIST) {
            try {
                ObjectNode node = scrapeTechnical(w[0], w[1]);
                enrichWithPriceStats(node, w[0]);
                node.put("minkabu_url", "https://minkabu.jp/stock/" + w[0] + "/analyst_consensus");
                Double ratio = creditRatios.get(w[0]);
                if (ratio != null) {
                    node.put("credit_ratio", ratio);
                    // 信用倍率(買残/売残)が低い(=空売りが相対的に多い)ほど、将来の踏み上げ(ショートカバー)
                    // による上昇余地が大きいと一般に言われる。1倍未満を目安の閾値として単純な
                    // しきい値判定のみで機械的に付与する(LLM判断は使わない)。
                    node.put("squeeze_potential", ratio < 1.0);
                } else {
                    node.putNull("credit_ratio");
                    node.putNull("squeeze_potential");
                }
                technical.add(node);
            } catch (Exception e) {
                System.err.println("[WARN] technical fetch failed for " + w[0] + ": " + e);
            }
        }
        // ---- セクター(業種)平均との比較・逆行高検知 ----
        // 2026-08-02: 「相場環境の俯瞰」機能追加。SECTOR_MAPで同一業種とみなされる銘柄群の
        // change_pct平均と比較し、セクター全体が軟調な中で単独で強い(逆行高)銘柄を検知する。
        try {
            annotateSectorComparison(technical);
        } catch (Exception e) {
            System.err.println("[WARN] sector comparison failed: " + e);
        }

        root.set("technical", technical);
        if (technical.size() == WATCHLIST.length) {
            markUpdated(root, "technical", generatedAt);
        } else if (technical.size() > 0) {
            markPartial(root, "technical", generatedAt,
                "監視銘柄" + WATCHLIST.length + "件中" + technical.size() + "件を取得。一部は取得不可です。");
        } else {
            markUnavailable(root, "technical", generatedAt, "テクニカル指標を取得できませんでした。");
        }

        // ---- 成長株候補(TDnet「業績予想の修正」開示のうち好材料のみを機械的に抽出) ----
        ArrayNode growth = null;
        try {
            growth = scrapeGrowthCandidates(8, 8);
            // ダブルシグナル判定は表示用disclosures(直近20件程度)ではなく、
            // 別途もっと深くページを遡って「決算」タグの会社名だけを集めた専用セットを使う
            // (取りこぼしを減らすための無料の改善。詳細はscrapeKessanCompanies()のJavadoc参照)。
            java.util.Set<String> kessanCompanies = scrapeKessanCompanies(10, 150);
            markDoubleSignals(growth, kessanCompanies);
            root.set("growth_candidates", growth);
            if (growth.size() > 0) {
                markUpdated(root, "growth_candidates", generatedAt);
            } else {
                markEmpty(root, "growth_candidates", generatedAt, "取得済み・該当する好材料開示はありません。");
            }
        } catch (Exception e) {
            markUnavailable(root, "growth_candidates", generatedAt, "成長株候補を取得できませんでした。");
            System.err.println("[WARN] growth candidates fetch failed: " + e);
        }
        // 注: 4項目5段階スコアリング(材料・テクニカル・需給・期待値)は、Gemini補完後
        // (news_analyzer.pyが付与するtheme/baked_in_warning等)のフィールドも使いたいため、
        // このJavaの時点ではなく、パイプライン最後段のrender_dashboard.py側で
        // 表示直前にルールベース(LLM不使用)で計算する。

        // ---- 決算前 先行材料ウォッチ(Google News RSS・無料/キー不要・LLM不使用) ----
        // 好決算・ストップ高になる銘柄は、決算発表の当日いきなり材料が出るのではなく、
        // 四半期の途中で「増産」「受注拡大」「工場増強」等の断片ニュースが先行することが多い
        // (例: パナソニックHDのAIインフラ関連増産・増設報道が2026年7月の決算発表の1〜2か月前から出ていた)。
        // ここではLLMによる要約・判定は一切行わず、Google News RSS(無料・APIキー不要)の見出しに
        // 固定キーワードが含まれるかどうかだけで機械的に抽出する。
        try {
            ArrayNode watch = scrapePreEarningsWatch(2, 15, 14);
            root.set("pre_earnings_watch", watch);
            if (watch.size() > 0) {
                markUpdated(root, "pre_earnings_watch", generatedAt);
            } else {
                markEmpty(root, "pre_earnings_watch", generatedAt, "取得済み・該当する先行材料ニュースはありません。");
            }
        } catch (Exception e) {
            markUnavailable(root, "pre_earnings_watch", generatedAt, "決算前材料ウォッチを取得できませんでした。");
            System.err.println("[WARN] pre-earnings watch fetch failed: " + e);
        }

        // ---- EDINET 大量保有報告書(5%ルール)の簡易チェック(プロトタイプ) ----
        // EDINET APIは利用登録とAPIキーが必要なため、未設定時も前回値は使わず、
        // 当回は「取得不可」として空配列を表示する。
        try {
            String edinetApiKey = System.getenv("EDINET_API_KEY");
            if (edinetApiKey == null || edinetApiKey.isBlank()) {
                markUnavailable(root, "edinet_large_holdings", generatedAt,
                    "EDINET_API_KEYが未設定のため取得できませんでした。");
                System.err.println("[INFO] EDINET_API_KEY未設定のため、大量保有報告書チェックを取得不可として記録します。");
            } else {
                ArrayNode holdings = fetchEdinetLargeHoldings(WATCHLIST, edinetApiKey, 3);
                root.set("edinet_large_holdings", holdings);
                if (holdings.size() > 0) {
                    markUpdated(root, "edinet_large_holdings", generatedAt);
                } else {
                    markEmpty(root, "edinet_large_holdings", generatedAt, "取得済み・該当する大量保有報告書はありません。");
                }
            }
        } catch (Exception e) {
            markUnavailable(root, "edinet_large_holdings", generatedAt, "EDINET大量保有報告書を取得できませんでした。");
            System.err.println("[WARN] EDINET large holdings check failed: " + e);
        }

        // ---- 経済カレンダー(重要度) ----
        // FOMC・日銀金融政策決定会合は年間スケジュールが公式サイトで事前公表されているため、
        // 決め打ちの日程テーブル(FOMC_2026 / BOJ_2026)を保持する。米雇用統計は「原則毎月第1金曜日」
        // というBLSの運用ルールに基づき当日時点から向こう6か月分を計算する(祝日・政府機関閉鎖等に
        // より実際の発表日が前後する可能性があるため note で注記する、ベストエフォート機能)。
        try {
            ArrayNode calendar = buildEconomicCalendar();
            root.set("economic_calendar", calendar);
            if (calendar.size() > 0) {
                markUpdated(root, "economic_calendar", generatedAt);
            } else {
                markEmpty(root, "economic_calendar", generatedAt, "取得済み・今後の経済イベントはありません。");
            }
        } catch (Exception e) {
            markUnavailable(root, "economic_calendar", generatedAt, "経済カレンダーを作成できませんでした。");
            System.err.println("[WARN] economic calendar build failed: " + e);
        }

        // overnight_news / afterclose_news / movers_morning / movers_afterclose / us_good_news は
        // news_analyzer.py が同一実行内で必ず空配列または新規取得結果へ更新する。
        // このJava処理開始時点で前回値を消去済みのため、更新失敗時に古い内容が残ることはない。

        MAPPER.writerWithDefaultPrettyPrinter().writeValue(dataFile, root);
        System.out.println("[OK] data.json updated (mode=" + mode + ")");
    }

    /**
     * 当回の処理開始時に、表示・通知に使う前回値と前回の更新時刻を必ず消去する。
     * 取得できなかったデータは空配列または空オブジェクトのまま、data_statusで
     * 「取得不可」と明示される。これにより、失敗時に古い内容が残る経路を遮断する。
     */
    private static void resetStaleData(ObjectNode root, String checkedAt) {
        for (String field : new String[] {
            "tdnet_morning", "tdnet_afterclose", "technical", "growth_candidates",
            "pre_earnings_watch", "overnight_news", "afterclose_news", "movers_morning",
            "movers_afterclose", "us_good_news", "edinet_large_holdings", "economic_calendar"
        }) {
            root.set(field, MAPPER.createArrayNode());
        }
        root.set("us_market", MAPPER.createObjectNode());
        root.set("fx", MAPPER.createObjectNode());
        root.set("nikkei225", MAPPER.createObjectNode());
        root.set("nikkei_futures", MAPPER.createObjectNode());
        root.set("data_updated_at", MAPPER.createObjectNode());

        ObjectNode statuses = MAPPER.createObjectNode();
        for (String field : TRACKED_FIELDS) {
            ObjectNode status = MAPPER.createObjectNode();
            status.put("state", "pending");
            status.put("checked_at", checkedAt);
            status.put("message", "更新処理中です。");
            statuses.set(field, status);
        }
        root.set("data_status", statuses);
    }

    /** データ種別ごとの当回の取得状態・確認時刻・理由を保存する。 */
    private static void setDataStatus(ObjectNode root, String field, String state, String checkedAt, String message) {
        ObjectNode statuses = root.has("data_status") && root.get("data_status").isObject()
            ? (ObjectNode) root.get("data_status")
            : MAPPER.createObjectNode();
        ObjectNode status = MAPPER.createObjectNode();
        status.put("state", state);
        status.put("checked_at", checkedAt);
        status.put("message", message);
        statuses.set(field, status);
        root.set("data_status", statuses);
    }

    /** 正常に取得できたデータの更新時刻と状態を保存する。 */
    private static void markUpdated(ObjectNode root, String field, String updatedAt) {
        ObjectNode timestamps = root.has("data_updated_at") && root.get("data_updated_at").isObject()
            ? (ObjectNode) root.get("data_updated_at")
            : MAPPER.createObjectNode();
        timestamps.put(field, updatedAt);
        root.set("data_updated_at", timestamps);
        setDataStatus(root, field, "updated", updatedAt, "今回の実行で取得・更新しました。");
    }

    /** 一部の項目だけを取得できた場合は、取得済み部分と不足を併記する。 */
    private static void markPartial(ObjectNode root, String field, String checkedAt, String message) {
        markUpdated(root, field, checkedAt);
        setDataStatus(root, field, "partial", checkedAt, message);
    }

    /** 取得処理は成功し、該当データがなかった場合を記録する。 */
    private static void markEmpty(ObjectNode root, String field, String checkedAt, String message) {
        markUpdated(root, field, checkedAt);
        setDataStatus(root, field, "empty", checkedAt, message);
    }

    /** 取得できなかったデータは空のまま、理由を記録する。 */
    private static void markUnavailable(ObjectNode root, String field, String checkedAt, String message) {
        setDataStatus(root, field, "unavailable", checkedAt, message);
    }

    /** 今回の実行対象外のデータは、前回値を使わず未更新として記録する。 */
    private static void markNotRequested(ObjectNode root, String field, String checkedAt, String message) {
        setDataStatus(root, field, "not_requested", checkedAt, message);
    }

    // ---------------- 市場指標 ----------------

    /** us_market.sp500 のような1階層ネストしたオブジェクトを更新する */
    private static boolean updateNested(ObjectNode root, String parentField, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return false; // 呼び出し側で当回の取得不可として記録
        ObjectNode parent = root.has(parentField) && root.get(parentField).isObject()
            ? (ObjectNode) root.get(parentField)
            : MAPPER.createObjectNode();
        parent.set(field, target);
        root.set(parentField, parent);
        return true;
    }

    /** fx / nikkei225 / nikkei_futures のようなトップレベル直下のフィールドを更新する */
    private static boolean updateTopLevel(ObjectNode root, String field, String symbol, boolean isFx) {
        ObjectNode target = MAPPER.createObjectNode();
        if (!fillQuote(target, symbol, isFx)) return false; // 呼び出し側で当回の取得不可として記録
        root.set(field, target);
        return true;
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

            // 注: meta.chartPreviousCloseは「range引数(ここでは5d)のチャート開始日より前の終値」であり、
            // 直近の営業日の終値とは異なる(例: 週末を挟むと1週間近く前の値になり得る)。
            // また実際にはmeta.previousCloseフィールド自体がこのAPIのレスポンスに含まれないことが多く、
            // これを優先条件にしても実質的にchartPreviousCloseへフォールバックし続けてしまう。
            // そこで「前営業日比」には、日次ローソク足配列(indicators.quote[0].close)の
            // 「直近から2番目の終値」を使う。配列の最後の要素は直近の取引日(=regularMarketPriceの日)の
            // 終値(取引時間中は未確定でnullの場合もある)、その1つ前が正しい「前営業日の終値」になる。
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
            // 万一日次終値配列が取得できない場合のみ、従来のchartPreviousCloseにフォールバックする
            // (精度は落ちるが、値を丸ごと諦めるよりは良い)。
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
            // 注: 日付ラベルには「取得した今この瞬間」ではなく、実際にこの値が観測された時刻
            // (meta.regularMarketTime、取引中の指標はその時点、取引終了後の指標は直近終値の時刻)を使う。
            // 土日や祝日にジョブを走らせても、実際の最終取引日の日付が正しく表示されるようにするため。
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

    // ---------------- 成長株候補(決算・好材料ベース) ----------------

    /**
     * 既存の主力ウォッチリストは値位置が高めのため、別枠で「決算・好材料に基づく成長株候補」を
     * 機械的に抽出する。
     *
     * 判定方法: TDnetの「業績予想の修正」開示(株探の category_group=mod_forecast 一覧)の
     * タイトル文言に、上方修正・増配など明確な好材料キーワードが含まれ、かつ下方修正・特別損失
     * などの悪材料キーワードを含まない開示だけを採用する。
     * 「決算が良い」「好材料がある」という判断そのものをLLMや主観に頼らず、
     * 会社が実際にTDnetへ開示した文言のキーワードマッチのみで機械的・決定論的に判定するため、
     * 每回の自動実行でも再現性がある。各候補には実際の開示PDFへの直リンクを必ず添付し、
     * 根拠を開示原文で確認できるようにする。
     */
    private static ArrayNode scrapeGrowthCandidates(int maxPages, int maxResults) {
        ArrayNode out = MAPPER.createArrayNode();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)、(.*?)\\s*(業修)?\\s*(今日|明日|\\d{1,2}/\\d{1,2}|\\d{1,2}月\\d{1,2}日\\([月火水木金土日]\\))\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
        );
        String[] positiveKeywords = {"上方修正", "増配", "特別配当", "復配", "増額"};
        String[] negativeKeywords = {"下方修正", "減配", "減額", "無配", "特別損失"};

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
                if (!m.matches()) continue; // 会社名が特定できない行は根拠不明として除外

                String company = m.group(1).trim();
                String title = m.group(2).trim();
                String date = m.group(4);
                String time = m.group(5);
                if (company.isEmpty() || company.equals("―") || seenCompanies.contains(company)) continue;
                seenCompanies.add(company);

                ObjectNode row = MAPPER.createObjectNode();
                row.put("company", company);
                row.put("title", title);
                row.put("catalyst", matchedKeyword);
                row.put("reason", "TDnet適時開示「" + title + "」より、" + matchedKeyword + "を確認。");
                row.put("asof", date + " " + time);
                row.put("url", a.absUrl("href"));
                out.add(row);
            }
        }
        return out;
    }

    /**
     * scrapeGrowthCandidates()が抽出した「業績予想の修正(上方修正等)」候補について、
     * 同じ会社名がkessanCompanies(直近の「決算」タグ開示会社名セット)にも含まれる場合、
     * double_signal=trueを付与する。
     *
     * 四半期の好決算(決算短信)と通期ガイダンスの上方修正が同時に発表されるパターンは、
     * 単独の好決算開示よりもストップ高との相関が強いという分析結果(2026年7月のパナソニックHD
     * 決算・ストップ高の事後分析)に基づく、無料データのみでの機械的な近似実装。
     *
     * kessanCompaniesはscrapeKessanCompanies()でより深くページを遡って集めたセットを渡す想定
     * (表示用disclosuresの直近20件程度だけだと取りこぼしが多いため)。
     */
    private static void markDoubleSignals(ArrayNode growth, java.util.Set<String> kessanCompanies) {
        if (growth == null || kessanCompanies == null) return;
        for (JsonNode g : growth) {
            if (!(g instanceof ObjectNode)) continue;
            String company = g.path("company").asText("");
            ((ObjectNode) g).put("double_signal", kessanCompanies.contains(company));
        }
    }

    /**
     * ダブルシグナル判定専用に、株探の適時開示一覧(表示用disclosuresと同じ無料ソース)を
     * もっと深く(最大maxPagesページ・最大maxItems件)遡って、「決算」タグが付いた会社名だけを
     * 集めたセットを返す。
     *
     * 背景: 表示用のscrapeKabutanDisclosures()は「サイト全体での最新開示」上位20件程度しか
     * 保持しないため、他社の開示に押し流されて対象会社の「決算」開示が一覧から漏れ、
     * 実際には決算と上方修正を同時開示している会社でもdouble_signalを検知できない
     * (false negative)ケースがあった。本メソッドは表示件数を増やさずに、判定用の会社名セットだけを
     * より深いページ数まで遡って集めることで、追加の有料APIなしにこの取りこぼしを減らす。
     *
     * それでも1日の開示件数が非常に多い日はmaxPagesを超えて漏れる可能性があり、
     * 完全な取りこぼしゼロを保証するものではない(JPX公式の有料TDnet APIを使えば
     * 銘柄コード指定で確実に検索できるが、本ツールは無料ソースのみで運用する方針のため未導入)。
     */
    private static java.util.Set<String> scrapeKessanCompanies(int maxPages, int maxItems) {
        java.util.Set<String> companies = new java.util.HashSet<>();
        Pattern rowPattern = Pattern.compile(
            "^(.*?)、(.*?)\\s*(決算|配当|業修|自社|エク|追訂|他)?\\s*(今日|明日|\\d{1,2}/\\d{1,2})\\s+(\\d{1,2}:\\d{2})\\s*(New!)?$"
        );
        int seen = 0;
        for (int page = 1; page <= maxPages && seen < maxItems; page++) {
            String url = "https://s.kabutan.jp/disclosures/" + (page == 1 ? "" : "?page=" + page);
            Document doc;
            try {
                doc = Jsoup.connect(url).userAgent(UA).timeout(15000).get();
            } catch (Exception e) {
                System.err.println("[WARN] kabutan kessan-scan page " + page + " fetch failed: " + e);
                break;
            }
            List<Element> links = doc.select("a[href^=https://tdnet-pdf.kabutan.jp/]");
            if (links.isEmpty()) break;
            for (Element a : links) {
                if (seen >= maxItems) break;
                seen++;
                String text = a.text().trim();
                Matcher m = rowPattern.matcher(text);
                if (m.matches() && "決算".equals(m.group(3))) {
                    String company = m.group(1).trim();
                    if (!company.isEmpty() && !"―".equals(company)) {
                        companies.add(company);
                    }
                }
            }
        }
        return companies;
    }

    // ---------------- 決算前 先行材料ウォッチ(Google Newsの見出しキーワード抽出) ----------------

    private static final String[] PRE_EARNINGS_KEYWORDS = {
        "増産", "受注拡大", "受注", "新工場", "工場増強", "生産能力", "設備投資",
        "データセンター", "AI投資", "稼働開始", "増強", "量産開始"
    };

    /**
     * ウォッチリスト銘柄ごとにGoogle News RSS(無料・APIキー不要・登録不要)を検索し、
     * 「増産」「受注」「工場」「生産能力」「データセンター」等、決算に先行して出やすい
     * 好材料キーワードをタイトルに含む直近ニュースだけを機械的に抽出する。
     *
     * LLMによる要約・意味解釈は一切行わない(キーワード完全一致のみ)。あくまで
     * 「決算発表を待たずに関連ニュースの多寡を継続的に拾う」ための一次スクリーニング材料であり、
     * 見出しに一致しただけでは好材料の実際の大きさ・信頼性は判断できない。必ずリンク先の原文を
     * 確認すること。
     *
     * @param maxPerCompany 1銘柄あたりの採用件数上限
     * @param maxTotal      全体の採用件数上限
     * @param lookbackDays  何日前までの記事を対象にするか
     */
    private static ArrayNode scrapePreEarningsWatch(int maxPerCompany, int maxTotal, int lookbackDays) {
        ArrayNode out = MAPPER.createArrayNode();
        ZonedDateTime cutoff = ZonedDateTime.now(ZoneId.of("Asia/Tokyo")).minusDays(lookbackDays);

        for (String[] w : WATCHLIST) {
            if (out.size() >= maxTotal) break;
            String code = w[0];
            String name = w[1];
            try {
                String keywordClause = String.join(" OR ", PRE_EARNINGS_KEYWORDS);
                String rawQuery = "\"" + name + "\" (" + keywordClause + ")";
                String q = URLEncoder.encode(rawQuery, StandardCharsets.UTF_8);
                String url = "https://news.google.com/rss/search?q=" + q + "&hl=ja&gl=JP&ceid=JP:ja";
                Document doc = Jsoup.connect(url)
                    .userAgent(UA)
                    .timeout(15000)
                    .parser(Parser.xmlParser())
                    .get();
                Elements items = doc.select("item");
                int perCompany = 0;
                for (Element item : items) {
                    if (perCompany >= maxPerCompany || out.size() >= maxTotal) break;
                    Element titleEl = item.selectFirst("title");
                    Element linkEl = item.selectFirst("link");
                    Element pubDateEl = item.selectFirst("pubDate");
                    String title = titleEl != null ? titleEl.text() : "";
                    String link = linkEl != null ? linkEl.text() : "";
                    String pubDateStr = pubDateEl != null ? pubDateEl.text() : "";
                    if (title.isEmpty() || link.isEmpty() || pubDateStr.isEmpty()) continue;

                    ZonedDateTime pubDate;
                    try {
                        pubDate = ZonedDateTime.parse(pubDateStr, DateTimeFormatter.RFC_1123_DATE_TIME);
                    } catch (Exception e) {
                        continue; // 日付が解釈できない記事は対象外
                    }
                    if (pubDate.isBefore(cutoff)) continue;

                    String matched = null;
                    for (String kw : PRE_EARNINGS_KEYWORDS) {
                        if (title.contains(kw)) { matched = kw; break; }
                    }
                    if (matched == null) continue;

                    ObjectNode row = MAPPER.createObjectNode();
                    row.put("code", code);
                    row.put("company", name);
                    row.put("title", title);
                    row.put("url", link);
                    row.put("keyword", matched);
                    row.put("asof", pubDate.withZoneSameInstant(ZoneId.of("Asia/Tokyo"))
                        .format(DateTimeFormatter.ofPattern("M/d HH:mm")));
                    out.add(row);
                    perCompany++;
                }
            } catch (Exception e) {
                System.err.println("[WARN] pre-earnings watch fetch failed for " + code + ": " + e);
            }
        }
        return out;
    }

    // ---------------- 織り込み済みリスク判定用の補助データ ----------------

    /**
     * Yahoo Finance chart API(無料・キー不要、range=1yの日足)から、
     * 「直近5日騰落率」と「52週高値からの位置」を算出しnodeに追加する。
     *
     * 好決算・好材料であっても、発表前から株価が既に大きく上昇していたり、
     * 52週高値のすぐ近くにある場合は「材料出尽くし売り」のリスクが高いという
     * 経験則を、LLMではなく決定論的な数値として補助材料化するためのもの。
     * 実際の「材料出尽くしリスクの判定」自体はnews_analyzer.py側のGeminiプロンプトで行う
     * (ここでは無料の生データを提供するだけで、判断・スコアリングは行わない)。
     *
     * 失敗時は該当フィールドを付与しない(既存のscrapeTechnical()の結果はそのまま活かす)。
     */
    private static void enrichWithPriceStats(ObjectNode node, String code) {
        try {
            String symbol = code + ".T";
            String url = "https://query1.finance.yahoo.com/v8/finance/chart/" + symbol + "?interval=1d&range=1y";
            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .header("User-Agent", UA)
                .timeout(Duration.ofSeconds(15))
                .GET().build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) return;

            JsonNode json = MAPPER.readTree(res.body());
            JsonNode result = json.path("chart").path("result").get(0);
            if (result == null || result.isMissingNode()) return;
            JsonNode meta = result.path("meta");
            double currentPrice = meta.path("regularMarketPrice").asDouble(Double.NaN);

            JsonNode quote0 = result.path("indicators").path("quote").get(0);
            List<Double> closes = new java.util.ArrayList<>();
            for (JsonNode c : quote0.path("close")) {
                if (c.isNumber()) closes.add(c.asDouble());
            }
            List<Double> highs = new java.util.ArrayList<>();
            for (JsonNode h : quote0.path("high")) {
                if (h.isNumber()) highs.add(h.asDouble());
            }
            List<Double> opens = new java.util.ArrayList<>();
            for (JsonNode o : quote0.path("open")) {
                opens.add(o.isNumber() ? o.asDouble() : Double.NaN);
            }
            List<Double> volumes = new java.util.ArrayList<>();
            for (JsonNode v : quote0.path("volume")) {
                volumes.add(v.isNumber() ? v.asDouble() : Double.NaN);
            }

            // 直近5日騰落率: 日足終値配列の「直近から6番目」の終値を5営業日前の基準値とみなす
            // (配列の最後の要素は当日の未確定値であることが多いため、現在値には
            //  regularMarketPriceを使い、比較対象だけを終値配列から取る近似計算)。
            if (!Double.isNaN(currentPrice) && closes.size() >= 6) {
                double base = closes.get(closes.size() - 6);
                if (base != 0) {
                    double ret5d = (currentPrice - base) / base * 100.0;
                    node.put("ret_5d_pct", Math.round(ret5d * 100) / 100.0);
                }
            }

            // 52週高値からの位置: range=1yの日足高値の最大値を「52週高値」の近似値として使う。
            if (!Double.isNaN(currentPrice) && !highs.isEmpty()) {
                double high52w = java.util.Collections.max(highs);
                if (high52w > 0) {
                    double dist = (high52w - currentPrice) / high52w * 100.0;
                    node.put("high_52w", Math.round(high52w * 100) / 100.0);
                    node.put("high_52w_dist_pct", Math.round(dist * 100) / 100.0);
                }
            }

            // 2026-08-02: 「需給と勢いの可視化」機能追加。
            //   ・volume_ratio … 当日出来高 ÷ 直近5営業日平均出来高。2倍以上で「出来高急増」フラグ。
            //   ・gap_pct      … (当日始値 − 前日終値) ÷ 前日終値。寄り付き時点の需給の偏りの目安。
            // どちらもYahoo Finance chart API(range=1y日足)の同一レスポンス内のopen/volume配列から
            // 追加コストなしで算出できる(新規HTTPリクエスト不要)。
            try {
                if (volumes.size() >= 6) {
                    double todayVolume = volumes.get(volumes.size() - 1);
                    // 直近5営業日平均は「当日を除く」直前5日分(size-6 〜 size-2)を使う。
                    double sum = 0; int n = 0;
                    for (int i = volumes.size() - 6; i < volumes.size() - 1; i++) {
                        double v = volumes.get(i);
                        if (!Double.isNaN(v)) { sum += v; n++; }
                    }
                    if (!Double.isNaN(todayVolume) && n > 0) {
                        double avg5d = sum / n;                        if (avg5d > 0) {
                            double ratio = todayVolume / avg5d;
                            node.put("volume", (long) todayVolume);
                            node.put("avg_volume_5d", Math.round(avg5d));
                            node.put("volume_ratio", Math.round(ratio * 100) / 100.0);
                            node.put("volume_surge", ratio >= 2.0);
                        }
                    }
                }
            } catch (Exception e) {
                System.err.println("[WARN] volume ratio calc failed for " + code + ": " + e);
            }

            try {
                if (!opens.isEmpty() && closes.size() >= 2) {
                    double todayOpen = opens.get(opens.size() - 1);
                    double prevClose = closes.get(closes.size() - 2);
                    if (!Double.isNaN(todayOpen) && !Double.isNaN(prevClose) && prevClose != 0) {
                        double gapPct = (todayOpen - prevClose) / prevClose * 100.0;
                        node.put("gap_pct", Math.round(gapPct * 100) / 100.0);
                        // ±2%以上の寄り付きギャップを「窓開け」の目安として機械的にフラグ付けする。
                        node.put("gap_up", gapPct >= 2.0);
                        node.put("gap_down", gapPct <= -2.0);
                    }
                }
            } catch (Exception e) {
                System.err.println("[WARN] gap calc failed for " + code + ": " + e);
            }
        } catch (Exception e) {
            System.err.println("[WARN] price stats fetch failed for " + code + ": " + e);
        }
    }

    /**
     * ウォッチリスト銘柄をSECTOR_MAPの業種でグルーピングし、各銘柄に
     *   ・sector                … 業種名
     *   ・sector_avg_change_pct … 同業種内・自分を除く他銘柄のchange_pct平均(同業種が1銘柄のみの場合はnull)
     *   ・sector_contrarian     … 業種平均が下落しているにもかかわらず自分だけ強い上昇をしている「逆行高」フラグ
     * を付与する。あくまでウォッチリスト20銘柄内での相対比較であり、業種全体の統計ではない
     * (無料・キー不要で完結させるための簡易近似)。
     */
    private static void annotateSectorComparison(ArrayNode technical) {
        // 業種名 → その業種に属する change_pct のリスト(nullは除外)
        java.util.Map<String, List<Double>> sectorChanges = new java.util.HashMap<>();
        for (JsonNode n : technical) {
            String code = n.path("code").asText(null);
            if (code == null) continue;
            String sector = SECTOR_MAP.get(code);
            if (sector == null) continue;
            JsonNode cp = n.path("change_pct");
            if (cp.isNumber()) {
                sectorChanges.computeIfAbsent(sector, k -> new java.util.ArrayList<>()).add(cp.asDouble());
            }
        }

        for (JsonNode n : technical) {
            if (!(n instanceof ObjectNode)) continue;
            ObjectNode node = (ObjectNode) n;
            String code = node.path("code").asText(null);
            if (code == null) continue;
            String sector = SECTOR_MAP.get(code);
            if (sector == null) continue;
            node.put("sector", sector);

            List<Double> all = sectorChanges.get(sector);
            JsonNode cpNode = node.path("change_pct");
            if (all == null || !cpNode.isNumber()) {
                node.putNull("sector_avg_change_pct");
                node.put("sector_contrarian", false);
                continue;
            }
            double own = cpNode.asDouble();
            // 自分を除いた同業種平均(同業種が自分1銘柄のみの場合は比較不能としてnullを返す)。
            // 同値の重複による誤除外を避けるため、値ではなく「1件だけ除外する」方式にする。
            if (all.size() <= 1) {
                node.putNull("sector_avg_change_pct");
                node.put("sector_contrarian", false);
                continue;
            }
            double othersSum = 0; int othersCount = 0;
            boolean skippedOwn = false;
            for (double v : all) {
                if (!skippedOwn && v == own) { skippedOwn = true; continue; }
                othersSum += v; othersCount++;
            }
            if (othersCount == 0) {
                node.putNull("sector_avg_change_pct");
                node.put("sector_contrarian", false);
                continue;
            }
            double sectorAvg = othersSum / othersCount;
            node.put("sector_avg_change_pct", Math.round(sectorAvg * 100) / 100.0);

            // 逆行高: 業種平均が-0.3%以下(軟調)にもかかわらず、自分は+1.0%以上上昇しており、
            // かつその差が+1.5pt以上あるケースを機械的にフラグ付けする。
            boolean contrarian = sectorAvg <= -0.3 && own >= 1.0 && (own - sectorAvg) >= 1.5;
            node.put("sector_contrarian", contrarian);
        }
    }

    /**
     * EDINET API v2(https://api.edinet-fsa.go.jp/api/v2/documents.json)から、
     * 直近lookbackDays日分の提出書類一覧を取得し、大量保有報告書(docTypeCode=350)・
     * 変更報告書(docTypeCode=351)のうち、書類概要(docDescription)にウォッチリストの
     * 会社名が含まれるものをウォッチリスト銘柄と紐づけて返す。
     *
     * 注: EDINET APIはVersion 2から利用登録(無料・電話番号必須)とAPIキーが必須になっており、
     * 呼び出し元でEDINET_API_KEYが未設定の場合はそもそもこのメソッドを呼ばない前提。
     * また対象銘柄の特定は構造化フィールドではなく書類概要の文字列一致による簡易判定のため、
     * 会社名の表記ゆれ(「株式会社」の有無等)によって取りこぼす可能性があるプロトタイプ実装である。
     */
    private static ArrayNode fetchEdinetLargeHoldings(String[][] watchlist, String apiKey, int lookbackDays) {
        ArrayNode out = MAPPER.createArrayNode();
        ZonedDateTime today = ZonedDateTime.now(ZoneId.of("Asia/Tokyo"));
        DateTimeFormatter dateFmt = DateTimeFormatter.ofPattern("yyyy-MM-dd");

        for (int d = 0; d < lookbackDays; d++) {
            String dateStr = today.minusDays(d).format(dateFmt);
            try {
                String url = "https://api.edinet-fsa.go.jp/api/v2/documents.json?date=" + dateStr
                    + "&type=2&Subscription-Key=" + URLEncoder.encode(apiKey, StandardCharsets.UTF_8);
                HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .header("User-Agent", UA)
                    .timeout(Duration.ofSeconds(20))
                    .GET().build();
                HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
                if (res.statusCode() != 200) {
                    System.err.println("[WARN] EDINET documents.json fetch failed (date=" + dateStr + "): HTTP " + res.statusCode());
                    continue;
                }
                JsonNode json = MAPPER.readTree(res.body());
                JsonNode results = json.path("results");
                if (!results.isArray()) continue;

                for (JsonNode doc : results) {
                    String docTypeCode = doc.path("docTypeCode").asText("");
                    if (!"350".equals(docTypeCode) && !"351".equals(docTypeCode)) continue;
                    String docDescription = doc.path("docDescription").asText("");
                    String filerName = doc.path("filerName").asText("");
                    String submitDateTime = doc.path("submitDateTime").asText("");

                    for (String[] w : watchlist) {
                        String code = w[0];
                        String name = w[1];
                        // 「株式会社」等の法人格表記ゆれの影響を減らすため、比較前に簡易的に除去する
                        String simplifiedName = name.replace("株式会社", "").replace("(株)", "");
                        if (docDescription.contains(name) || (!simplifiedName.isBlank() && docDescription.contains(simplifiedName))) {
                            ObjectNode row = MAPPER.createObjectNode();
                            row.put("code", code);
                            row.put("name", name);
                            row.put("filer_name", filerName);
                            row.put("doc_description", docDescription);
                            row.put("doc_type", "351".equals(docTypeCode) ? "変更報告書" : "大量保有報告書");
                            row.put("submit_datetime", submitDateTime);
                            out.add(row);
                            break; // 1書類につき1銘柄のみ紐づけ(複数銘柄名が偶然含まれるケースの重複防止)
                        }
                    }
                }
            } catch (Exception e) {
                System.err.println("[WARN] EDINET fetch/parse failed (date=" + dateStr + "): " + e);
            }
        }
        return out;
    }

    // 2026年のFOMC(米連邦公開市場委員会)開催日程(公式: federalreserve.gov/monetarypolicy/fomccalendars.htm、
    // 2026-08-03時点で確認)。会合最終日(政策発表日)を記載。
    private static final String[][] FOMC_2026 = {
        {"2026-01-28", "FOMC(米連邦公開市場委員会)政策発表"},
        {"2026-03-18", "FOMC(米連邦公開市場委員会)政策発表・SEP(経済見通し)公表"},
        {"2026-04-29", "FOMC(米連邦公開市場委員会)政策発表"},
        {"2026-06-17", "FOMC(米連邦公開市場委員会)政策発表・SEP(経済見通し)公表"},
        {"2026-07-29", "FOMC(米連邦公開市場委員会)政策発表"},
        {"2026-09-16", "FOMC(米連邦公開市場委員会)政策発表・SEP(経済見通し)公表"},
        {"2026-10-28", "FOMC(米連邦公開市場委員会)政策発表"},
        {"2026-12-09", "FOMC(米連邦公開市場委員会)政策発表・SEP(経済見通し)公表"},
    };

    // 2026年の日銀金融政策決定会合日程(公式: boj.or.jp/mopo/mpmsche_minu/index.htm、
    // 2026-08-03時点で確認)。会合最終日(政策公表日)を記載。
    private static final String[][] BOJ_2026 = {
        {"2026-01-23", "日銀金融政策決定会合・「経済・物価情勢の展望」公表"},
        {"2026-03-19", "日銀金融政策決定会合"},
        {"2026-04-28", "日銀金融政策決定会合・「経済・物価情勢の展望」公表"},
        {"2026-06-16", "日銀金融政策決定会合"},
        {"2026-07-31", "日銀金融政策決定会合・「経済・物価情勢の展望」公表"},
        {"2026-09-18", "日銀金融政策決定会合"},
        {"2026-10-30", "日銀金融政策決定会合・「経済・物価情勢の展望」公表"},
        {"2026-12-18", "日銀金融政策決定会合"},
    };

    /**
     * 経済カレンダー(重要度)を組み立てる。
     * FOMC・日銀会合は年間スケジュールが公式サイトで事前公表されているため決め打ちテーブルを使用し、
     * 米雇用統計は「原則毎月第1金曜日」というBLSの運用ルールから当日時点で向こう6か月分を計算する
     * (祝日・政府機関閉鎖等により実際の発表日が前後する可能性があるため note で注記する)。
     * 過去日は表示しても意味がないため、当日以降の直近イベントのみを対象とし、日付昇順に並べる。
     */
    private static ArrayNode buildEconomicCalendar() {
        java.time.LocalDate todayDate = ZonedDateTime.now(ZoneId.of("Asia/Tokyo")).toLocalDate();
        DateTimeFormatter dateFmt = DateTimeFormatter.ofPattern("yyyy-MM-dd");
        List<ObjectNode> items = new java.util.ArrayList<>();

        for (String[] row : FOMC_2026) {
            try {
                java.time.LocalDate d = java.time.LocalDate.parse(row[0]);
                if (d.isBefore(todayDate)) continue;
                ObjectNode item = MAPPER.createObjectNode();
                item.put("date", row[0]);
                item.put("event", row[1]);
                item.put("importance", 5);
                item.put("note", "日本時間深夜に結果発表。市場変動が大きくなりやすい。");
                items.add(item);
            } catch (Exception e) {
                System.err.println("[WARN] FOMC calendar row parse failed: " + row[0] + " " + e);
            }
        }

        for (String[] row : BOJ_2026) {
            try {
                java.time.LocalDate d = java.time.LocalDate.parse(row[0]);
                if (d.isBefore(todayDate)) continue;
                ObjectNode item = MAPPER.createObjectNode();
                item.put("date", row[0]);
                item.put("event", row[1]);
                item.put("importance", 5);
                item.put("note", "金融政策の変更有無・総裁会見の内容次第で為替・日本株が大きく動く可能性。");
                items.add(item);
            } catch (Exception e) {
                System.err.println("[WARN] BOJ calendar row parse failed: " + row[0] + " " + e);
            }
        }

        try {
            java.time.LocalDate cursor = todayDate.withDayOfMonth(1);
            for (int m = 0; m < 6; m++) {
                java.time.LocalDate firstFriday = cursor;
                while (firstFriday.getDayOfWeek() != java.time.DayOfWeek.FRIDAY) {
                    firstFriday = firstFriday.plusDays(1);
                }
                if (!firstFriday.isBefore(todayDate)) {
                    ObjectNode item = MAPPER.createObjectNode();
                    item.put("date", firstFriday.format(dateFmt));
                    item.put("event", "米雇用統計(非農業部門雇用者数・失業率)");
                    item.put("importance", 4);
                    item.put("note", "原則毎月第1金曜発表(祝日等により前後する場合あり)。日本時間21:30または22:30。");
                    items.add(item);
                }
                cursor = cursor.plusMonths(1);
            }
        } catch (Exception e) {
            System.err.println("[WARN] US employment calendar computation failed: " + e);
        }

        items.sort((a, b) -> a.path("date").asText("").compareTo(b.path("date").asText("")));

        ArrayNode out = MAPPER.createArrayNode();
        for (ObjectNode item : items) {
            out.add(item);
        }
        return out;
    }

    /**
     * JPX公式「銘柄別信用取引週末残高」(無料・登録不要・公式統計、毎週火曜16:30頃更新)のPDFから
     * 指定銘柄群の信用倍率(買残高÷売残高)を算出する。
     *
     * 民間サイト(みんかぶ・株探等)のスクレイピングには規約上の制約があるため、
     * 取引所自身が一般公開しているPDF統計資料を直接パースする方式を採用している。
     * データはCSV等ではなくPDFのみで提供されるため、PDFBoxでテキスト抽出したうえで、
     * 「(5桁化された証券コード) (ISIN) (売残高) (前週比) (買残高) (前週比)」という
     * 表の行パターンを正規表現で拾う。
     *
     * 注1: 2026年からの新証券コード5桁化に伴い、PDF内のコード表記は
     *      「4桁の証券コード + 末尾に0を付与した5桁」になっている
     *      (例: トヨタ自動車 7203 → 72030)。
     * 注2: 週次更新のため、最新でも数営業日のタイムラグがある(即時性は低いが無料で取れる公式データ)。
     * 注3: 何らかの理由で取得・解析に失敗した銘柄は結果マップに含めない(呼び出し側でnull扱いにする)。
     */
    private static java.util.Map<String, Double> fetchJpxCreditRatios(String[] codes) {
        java.util.Map<String, Double> out = new java.util.HashMap<>();
        try {
            String indexUrl = "https://www.jpx.co.jp/markets/statistics-equities/margin/05.html";
            HttpRequest req = HttpRequest.newBuilder(URI.create(indexUrl))
                .header("User-Agent", UA)
                .timeout(Duration.ofSeconds(20))
                .GET().build();
            HttpResponse<String> res = HTTP.send(req, HttpResponse.BodyHandlers.ofString());
            if (res.statusCode() != 200) return out;

            // ページ内に掲載されている(直近5週分程度の)PDFリンクのうち、
            // ファイル名の日付(YYYYMMDD)が最大のもの=最新分を採用する。
            // 注: JPXサイトのリンクは相対パス("/markets/.../syumatsuYYYYMMDD00.pdf")で
            //     出力されているため、絶対URL・相対URLの両方を許容する。
            Matcher pdfM = Pattern.compile(
                "href=\"(?:https://www\\.jpx\\.co\\.jp)?(/markets/statistics-equities/margin/[^\"]+/syumatsu(\\d{8})00\\.pdf)\""
            ).matcher(res.body());
            String latestUrl = null;
            String latestDate = "";
            while (pdfM.find()) {
                String u = pdfM.group(1);
                String d = pdfM.group(2);
                if (d.compareTo(latestDate) > 0) {
                    latestDate = d;
                    latestUrl = u;
                }
            }
            if (latestUrl != null && latestUrl.startsWith("/")) {
                latestUrl = "https://www.jpx.co.jp" + latestUrl;
            }
            if (latestUrl == null) {
                System.err.println("[WARN] jpx margin: latest PDF link not found");
                return out;
            }

            HttpRequest pdfReq = HttpRequest.newBuilder(URI.create(latestUrl))
                .header("User-Agent", UA)
                .timeout(Duration.ofSeconds(30))
                .GET().build();
            HttpResponse<byte[]> pdfRes = HTTP.send(pdfReq, HttpResponse.BodyHandlers.ofByteArray());
            if (pdfRes.statusCode() != 200) return out;

            String text;
            try (PDDocument doc = PDDocument.load(pdfRes.body())) {
                text = new PDFTextStripper().getText(doc);
            }

            for (String code : codes) {
                try {
                    Pattern rowP = Pattern.compile(
                        Pattern.quote(code + "0") + "\\s+JP[0-9A-Z]{10}\\s+([\\d,]+)\\s+(?:[▲△]\\s*)?[\\d,]+\\s+([\\d,]+)\\s+(?:[▲△]\\s*)?[\\d,]+"
                    );
                    Matcher rm = rowP.matcher(text);
                    if (rm.find()) {
                        double sell = Double.parseDouble(rm.group(1).replace(",", ""));
                        double buy = Double.parseDouble(rm.group(2).replace(",", ""));
                        if (sell > 0) {
                            out.put(code, Math.round((buy / sell) * 100) / 100.0);
                        }
                    }
                } catch (Exception e) {
                    System.err.println("[WARN] jpx margin parse failed for " + code + ": " + e);
                }
            }
        } catch (Exception e) {
            System.err.println("[WARN] jpx margin ratio fetch failed: " + e);
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
