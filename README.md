# Telegram Topic Monitor

用你自己的 Telegram 帳號透過 MTProto 監控你已加入的群組／頻道：

- 命中指定關鍵字時，立即傳到你的 **Saved Messages**。
- 可回掃指定日期之後的歷史訊息。
- 每日摘要按群組整理，並保留可用的原訊息連結。
- 命中訊息和 Telegram session 的**本機副本**存在這台電腦的 `data/`、`session/`；兩者都已被 `.gitignore` 排除。提醒與摘要會傳到你設定的 Telegram 目的地，並可選擇同步到 Slack。

## 安全與範圍

這個工具只會讀取你本來就有權限讀取的普通 Telegram 群組或頻道。它不會繞過群組權限，也不支援秘密聊天。請先確認你有權將該群組對話內容作個人整理，特別是工作或私人社群。

`TG_API_HASH`、登入驗證碼與 `session/telegram.session` 都是敏感資料；不要貼到聊天、截圖、雲端公開資料夾或 Git repository。

## 首次設定（Windows）

1. 安裝 Python 3.11+，在本資料夾開啟 PowerShell。
2. 安裝依賴：

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. 到 [Telegram API development tools](https://my.telegram.org/apps) 建立 API application，取得 `api_id` 與 `api_hash`。
4. 複製範本並填入值：

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

   `TG_CHATS` 強烈建議填指定群組，例如 `@my_group` 或 Telegram peer ID。留空代表會檢查帳號可讀的每一個群組／頻道。
5. 第一次登入會在**本機終端機**提示輸入 Telegram 驗證碼／兩步驟密碼，不要把它貼到這裡：

   ```powershell
   $env:PYTHONPATH = 'src'
   python -m tg_monitor login
   ```

登入成功後會產生 `session/telegram.session`。日後不必重複輸入驗證碼，除非你手動刪除 session 或 Telegram 要求重新登入。

## 通知目的地

預設 `TG_NOTIFY_CHAT=me`，也就是 Telegram Saved Messages。可改成你帳號能發文的指定 Telegram 群組／頻道：

```env
TG_NOTIFY_CHAT=@topic_alerts
```

或填 Telegram peer ID，例如私密 supergroup 常見的 `-100...`。目的地的所有成員都能看到轉送內容，請只選擇適合接收來源群組資訊的聊天室。

若需要同步到 Slack，在 Slack 建立 Incoming Webhook、選擇接收頻道後，將 webhook URL 填入 `.env`：

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

工具會同時送到 Telegram 和 Slack；Slack webhook URL 是機密，不能分享、截圖或提交到 Git。Slack 目的地以建立 webhook 時選擇的單一頻道為準。[Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)

## 使用方式

先回掃歷史訊息（`--since` 以 UTC 日期判斷；若要涵蓋澳洲悉尼當地 10 月 1 日，保守起見可填前一天）：

```powershell
$env:PYTHONPATH = 'src'
python -m tg_monitor scan-history --since 2026-10-01
```

持續監控新訊息。它會把每一則新命中即時傳到 Saved Messages；保持此視窗開啟，按 `Ctrl+C` 停止：

```powershell
.\scripts\run-monitor.ps1
```

如需手動傳送某日摘要（預設為 `TG_TIMEZONE` 的今天），**先停止監控程式**，避免兩個程序同時使用同一個 Telegram session：

```powershell
.\scripts\run-daily-digest.ps1
# 或指定日期
$env:PYTHONPATH = 'src'
python -m tg_monitor digest --date 2026-10-22
```

## 即時提醒與每天自動摘要

長期監控程式本身會在 `TG_TIMEZONE` 的 `TG_DIGEST_TIME` 傳送**前一個完整日曆日**的摘要；分享版預設為北京時間（`Asia/Shanghai`）00:05。這避免每日摘要與監控程式同時開啟 Telegram session。

在 Windows「工作排程器」建立工作，讓監控程式在登入時自動啟動：

1. 建立基本工作，名稱例如 `Telegram topic monitor`，觸發條件選「使用者登入時」。
2. 動作選「啟動程式」。程式填 `powershell.exe`。
3. 引數填：

   ```text
   -NoProfile -ExecutionPolicy Bypass -File "完整路徑\tg-topic-monitor\scripts\run-monitor.ps1"
   ```

4. 「開始於」填 `tg-topic-monitor` 的完整路徑。

可先手動執行確認正常後，再用工作排程器啟動它；建議勾選「如果工作失敗，重新啟動」。兩個 PowerShell 啟動腳本會把 Python 的失敗狀態傳回排程器。

## 設定欄位

| 欄位 | 用途 |
| --- | --- |
| `TG_API_ID` / `TG_API_HASH` | Telegram API application 的私密憑證 |
| `TG_PHONE` | 含國碼的登入電話，例如 `+614...` |
| `TG_KEYWORDS` | 以逗號分隔的字詞或片語，英文不分大小寫 |
| `TG_CHATS` | 可選的群組 allowlist；`@username` 或 peer ID，以逗號分隔 |
| `TG_TIMEZONE` | 摘要使用的 IANA 時區，預設 `Asia/Shanghai`（北京時間） |
| `TG_DIGEST_TIME` | 摘要發送時間（`HH:MM`），預設 `00:05`，內容是前一完整日 |
| `TG_NOTIFY_CHAT` | Telegram 通知目的地；`me`、`@username` 或 peer ID，預設 `me` |
| `SLACK_WEBHOOK_URL` | 選填；將相同通知同步到設定該 URL 的 Slack 頻道 |

這個第一版是關鍵字／片語比對。若你想要「即使沒出現字面關鍵字、但語意在討論同一主題」的判斷，下一步可加入本機模型或你選擇的 AI API；那會改變資料是否離開這台電腦，因此我先沒有預設開啟。
