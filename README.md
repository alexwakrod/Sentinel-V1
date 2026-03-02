# Sentinel-V1: Triple-Redundant Crypto Engine
> High-frequency, asynchronous Discord sentinel designed for sub-second market monitoring and autonomous self-healing.

## ⚙️ System Architecture 
Most trading bots rely on a single point of failure. Sentinel-V1 utilizes a **Triple-Consensus Algorithm** to ensure absolute data integrity before triggering an alert:

1. **The Pulse (Binance Websockets):** Maintains a <10ms latency stream for real-time price monitoring.
2. **The Anchor (HTTP Polling):** Secondary RESTful fallback that verifies the Websocket hasn't dropped frames or entered a "Silent Void."
3. **The Ground Truth (Private API Node):** Authenticated account-level API check to calculate true slippage and account-specific ticker prices.

If the three nodes drift by more than a set threshold (e.g., >0.1%), the system ignores the trigger, preventing false positives during extreme volatility.

## 🚀 Key Features
* **Autonomous Self-Healing:** Integrated with a Master Monitor that detects Discord API timeouts (Error `10062`) and automatically injects deferral logic without manual patching.
* **Global Synchronization:** Utilizes Naive UTC (`datetime.utcnow().replace(tzinfo=None)`) for cross-timezone logic, ensuring expiration dates remain perfectly accurate regardless of the host server's location.
* **Automated Garbage Collection:** Background tasks autonomously purge expired targets from the SQL database to maintain 0% state bloat and ensure fast query times.
* **Neon UI:** Fully integrated with Discord Modals and dynamic select menus for a seamless, private user experience.

## 🛠️ Installation & Deployment

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/alexwakrod/sentinel-v1.git](https://github.com/alexwakrod/sentinel-v1.git)
   cd sentinel-v1
