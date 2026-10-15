# Demo guide - Parkomate Station, end to end

This guide shows the whole station in about 20 minutes, the way the client described the
factory (answers of 13 October 2026):

1. **The measuring device sends its data over Wi-Fi**, both devices on the same network, in the
   agreed JSON format.
2. **The same software runs on several PCs.** A person logs in, does the work, and at the end of
   the session that person's work is an **Excel sheet, sent by e-mail**.
3. **Faulty boards are repaired, tested again, then accepted or scrapped** - the new
   **Repair** tab.

What is real and what is simulated in the demo:

| Part | In the demo | In the factory |
|---|---|---|
| Screens, database, Excel report, e-mail | real | real |
| Measuring device (Wi-Fi JSON) | **real network link**; a simulator plays the device | the real device |
| ESP32 board, flashing | simulated - or a **real ESP32** with the bench test (step 2C) | real |
| Server whitelist + firmware download | simulated | Parkomate server (API still to be confirmed) |
| Communication test, sensor readings, QR camera | simulated | real board + camera |

The amber band and the **Simulation mode** chip are always shown while anything is simulated,
so a demo can never be taken for production.

---

## 1. Before the demo (once per PC, about 10 minutes)

### 1A. Install

**With the installer** (any Windows 10/11 PC): run `ParkomateStation-Setup-<version>.exe`.
It asks for this PC's **station name** (for example `STATION-01`, and `STATION-02` on the second
PC) and the **measuring device address** (type the Wi-Fi network, for example
`192.168.1.0/24`, if you do not know the exact address). Tick **Demo shortcuts**. At the end,
leave **Create the first administrator now** ticked.

**From the source code** (the developer laptop):
```
cd parkomate-station
uv sync
uv run python -m parkomate admin create
```

In the commands below, `parkomate` means:
* installed: `"C:\Program Files\Parkomate Station\parkomate.exe"` (or the Start-menu shortcuts);
* from source: `uv run python -m parkomate`.

### 1B. Check the PC

```
parkomate doctor
```
Every line says **OK**, **WARN** or **FAIL**. Before the demo there must be no FAIL. It also
prints the address the measuring device must send to, for example
`http://192.168.1.20:8765/measurement`.

### 1C. Settings, operators and e-mail

Start the station, log in with the administrator, click your initials (top right) → **Admin**.

1. **Settings → Station**: the station name (each PC a different name).
2. **Settings → Measuring device → Measuring device IP (or network)**: the address of the PC
   that plays the measuring device, or the whole Wi-Fi network (`192.168.1.0/24`). Packets
   from this PC itself are always accepted, so a one-laptop demo needs no change here.
3. **Operators**: add one operator account per person (for example `OP1`).
4. **E-mail with Gmail** (the demo account):
   1. In the Google account: **Security → 2-Step Verification** must be on, then
      **App passwords** → create one called *Parkomate* → copy the 16-letter password.
   2. **Settings → Report e-mail**: *Send report e-mail* on, recipients (comma separated),
      sender address = the Gmail address, SMTP server `smtp.gmail.com`, SMTP port `587`,
      connection security `starttls`, user name empty (= sender). **Save settings**.
   3. **Passwords and tokens**: choose `smtp_password`, paste the app password,
      **Store in Credential Manager** (it never goes into a file). Same from a command window:
      `parkomate secrets set smtp_password`.
   4. **Reports & e-mail → Send test e-mail**. The recipients must receive it. If not, the
      message says why (wrong password, no internet, ...).

### 1D. Windows firewall

The installer opens TCP port **8765** for the station. When you run from the source code,
Windows asks the first time the station listens: tick **Private networks** and press
**Allow access**.

---

## 2. Start the demo

Pick one of three set-ups. All three use the real Wi-Fi link for the measuring device.

### 2A. One laptop (simplest)
Station and measuring device on the same PC. Start the station
(Start menu **Parkomate Station - DEMO with Wi-Fi measuring device**, or):
```
parkomate --mock --real-measuring-device
```
In a second window start the measuring device simulator:
```
parkomate measuring-device --to 127.0.0.1
```

### 2B. Two laptops on the same Wi-Fi (closest to the factory)
A phone hotspot is fine. Laptop 1 runs the station as in 2A. Laptop 2 runs only the simulator
(Start menu **Measuring device simulator**; it asks for the station's IP address):
```
parkomate measuring-device --to <IP of laptop 1>
```
The IP of laptop 1 is shown by `parkomate doctor`, by `ipconfig`, and on the Testing screen
while it waits ("Measuring device sends to http://...").

### 2C. With a real ESP32 board
Plug the ESP32 in by USB. Then the board is really flashed with the Blink test build (the LED
blinks afterwards); the measuring device still comes over Wi-Fi:
```
parkomate --bench-test --firmware-dir firmware\esp32-blink --real-measuring-device
```

The simulator window shows these keys:

| Key | Sends | Result on the station |
|---|---|---|
| **Enter** | a good measurement | all values green |
| **1** | V_A too high (24.40 V) | reject, box B |
| **2** | V_B too low (4.70 V) | reject, box B |
| **3** | V_C too low (3.10 V) | reject, box B |
| **4** | regulator too hot (ambient + 6 °C) | reject, box B |
| **q** | quit | |

After each press it says what the station answered: *used*, *not waiting*, *refused* ...

---

## 3. The demo script

### Part 1 - Log in (the person's session starts)
1. Log in as the operator (`OP1`).
2. The station measures the **ambient temperature** first: it waits up to 20 s for a packet.
   Press **Enter** in the simulator. (If you miss it, the station still opens; press **F9**
   later to re-measure.)

### Part 2 - A good board, through all four stages
1. **A Programming**: **Connect board** → the MAC is checked on the whitelist → **Upload
   firmware** (progress bar) → **Submit and next**.
2. **B Testing**: the communication test runs by itself. Press **Read sensor** 5 times, mark
   **sensor OK** and **indicator OK**. The station now says *Waiting for the measuring
   device…* and shows the address. **Press Enter in the simulator.** The four values turn
   green → **Submit and next**.
3. **C Labeling**: the QR code is read and the device ID is checked. Tick the 4 checks
   (**F1–F4**) → **Submit and next**.
4. **D Packaging**: tick the 4 checks → **Complete device**. Green bar, counter +1.

### Part 3 - A faulty board
1. Next board. In **B Testing**, when the station waits for the measuring device, press **3**
   in the simulator (V_C too low).
2. The screen turns **red**: *Place the device in reject box B*. Press **Device placed in box**.

### Part 4 - Repair: repaired → tested again → accepted
1. Top bar: switch **Production | Repair** to **Repair**. The board is in the list: box B,
   *Point C voltage*, with the measured value and the allowed range.
2. Under **Write what you repaired** choose, for example, *Voltage regulator replaced*, add a
   note (*U3 swapped*) and press **Save repair**.
3. Press **Test again** (bottom right). The station goes back to **A Programming** with a yellow
   bar *Retest of repaired board …*. Press **Connect board** - the station checks that it is
   the same board (same MAC) - and run all four stages again. In Testing press **Enter** in the
   simulator (good values).
4. After **Complete device** the station returns to the **Repair** tab: *Retest passed*.
   Press **Accept board** (green). The board leaves the open list (see **Closed**).

Optional - scrap: reject another board (key **4** = too hot), then on the Repair tab press
**Scrap board**, choose a reason (*Physical damage*), and press **Scrap board** again.

What the Repair tab enforces:
* **Test again** only after a repair was saved; the retest is the **whole line** (A → D).
* **Accept** only after a passed retest. **Scrap** at any time, with a reason.
* A board that fails its retest goes back to the list (*Needs repair*), with both faults shown.
* Every repair step is stored with the person and the session.

### Part 5 - End of session: Excel + e-mail
1. Click your initials → **Log out** → **End session**.
2. The summary shows the counts and *Report sent* (or *No connection - report saved, it will be
   sent automatically later*).
3. Open the report (**Open folder**, or `C:\ProgramData\Parkomate\reports`). The Excel file has
   **Summary, Devices, Checks, Rejections and Repairs** sheets. The Summary also counts the
   repaired boards tested again, the boards accepted after repair and the boards scrapped.
   First-pass yield does not count retests.
4. The same file arrives by e-mail.

### Part 6 - The second PC
Install the same Setup on a second PC with another station name (`STATION-02`). Another person
logs in there; their work is their own Excel and their own e-mail. A measuring device that
sends with `"station": "STATION-01"` is refused by `STATION-02` (so two stations on one Wi-Fi
network never mix up their data).

---

## 4. If something does not work

| What you see | What to do |
|---|---|
| Simulator: *No answer* | Wrong IP, the station is not running, or the firewall blocks port 8765 (see 1D). |
| Simulator: *Refused: this PC's address is not allowed* | Admin → Settings → Measuring device IP (or network): the simulator PC's IP, or the network (`192.168.1.0/24`). |
| Simulator: *Refused: this is station …* | Start the simulator with `--station <the station's name>`. |
| Simulator: *the station was not waiting* | Press the key only while the station says *Waiting for the measuring device…* (30 s), or at login. |
| *Not the board chosen for retest* | Another board was plugged in. Plug in the repaired board, or press **Cancel retest**. |
| E-mail not sent | Admin → Reports & e-mail → **Send test e-mail** shows the reason. Gmail needs the app password (1C). The report is kept and retried. |
| Anything else | `parkomate doctor`, and Admin → **Error log**. |

---

## 5. Honest limits of the demo

* The **server whitelist and firmware download** are simulated until the client gives the API
  (address, login, response format). The code for them exists and is tested with fakes.
* The **serial commands** to the board (PING, READ_SENSOR, GET_ID, SET_ID) and the **QR camera**
  are written but have not run against the production firmware and camera yet.
* **Repairs are per PC**: the Repair tab lists the boards rejected on *this* PC. Repairing a
  board on a different PC needs a shared database or the Parkomate server (open question).
* The repair actions and scrap reasons in the lists are our proposal - the client should check
  them.
