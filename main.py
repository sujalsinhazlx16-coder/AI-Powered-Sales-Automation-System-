import asyncio
import json
import os
import glob
import random
import datetime
import urllib.parse
from telethon import TelegramClient, events, Button
from core.ai_brain import AIBrain
from core.humanizer import Humanizer

# ─── Load Configuration ───────────────────────────────────────────────────────
with open("config.json", "r") as f:
    config = json.load(f)

API_ID   = int(config["api_id"])
API_HASH = config["api_hash"]

# ─── Initialize Core Components ──────────────────────────────────────────────
client    = TelegramClient("bot_session", API_ID, API_HASH)
brain     = AIBrain()
humanizer = Humanizer()

# ─── Admin Configuration ─────────────────────────────────────────────────────
ADMIN_USERNAMES = ["@Sujal_Sinha"]
ADMIN_IDS       = []

# ─── Business Logic & State Management (CRM) ─────────────────────────────────
USER_STATES           = {}  
REMINDER_TASKS        = {}  
PENDING_VERIFICATIONS = {}  
CRM_FILE              = "leads_crm.json"

if os.path.exists(CRM_FILE):
    with open(CRM_FILE, "r") as f:
        BUSINESS_METRICS = json.load(f)
else:
    BUSINESS_METRICS = {
        "total_revenue_inr": 0,
        "pipeline_value_inr": 0,
        "closed_won": 0,
        "active_leads": 0
    }

def save_crm_data():
    with open(CRM_FILE, "w") as f:
        json.dump(BUSINESS_METRICS, f, indent=4)

# ─── Asset Paths ─────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
CATALOGUE_PATH  = os.path.join(BASE_DIR, "assets", "event_packages.jpg") 
QR_CODE_PATH    = os.path.join(BASE_DIR, "assets", "qr_code.jpg")
TRUST_FOLDER    = os.path.join(BASE_DIR, "assets", "event_portfolio")

# ─── Message Templates ───────────────────────────────────────────────────────
TERMS_MESSAGE = """Event Booking Agreement & Terms 📋

Thank you for choosing us! Please note:
1. A 25% advance booking fee is required to permanently lock in your event date.
2. The advance is non-refundable if cancelled within 14 days.
3. The remaining balance is due 3 days prior.
4. Final guest headcount must be confirmed 1 week before."""

CATALOGUE_TEXT = """✨ Our Event Management Packages:

🎂 Social Events (Birthdays/Anniversaries)
• Classic Bash — ₹25,000
• Premium Party — ₹50,000

💍 Wedding Packages
• Silver Wedding — ₹1,50,000
• Gold Wedding — ₹3,00,000

🏢 Corporate Events
• Basic Meetup/Seminar — ₹40,000
• Grand Gala / Product Launch — ₹85,000"""

REMINDER_MESSAGES = [
    "Hi there! Just checking in — were you able to complete the advance payment to lock in your date? 😊",
    "Hello! We are getting inquiries for your date. Let us know if you'd like us to hold it! 📅",
    "The payment link is still active whenever you are ready! 🙌"
]


# ─── Helper Functions ─────────────────────────────────────────────────────────
def get_trust_pics(category="bday", count=2):
    subfolder = "wedding" if "wedding" in category.lower() else "bday"
    target_folder = os.path.join(TRUST_FOLDER, subfolder)
    
    if not os.path.exists(target_folder):
        target_folder = TRUST_FOLDER 

    pics = glob.glob(os.path.join(target_folder, "*.jpg")) + \
           glob.glob(os.path.join(target_folder, "*.jpeg")) + \
           glob.glob(os.path.join(target_folder, "*.png"))
    return random.sample(pics, min(count, len(pics))) if pics else []

def get_state(chat_id):
    if chat_id not in USER_STATES:
        USER_STATES[chat_id] = {
            "current_stage": "greeting",
            "personality": "soft_friendly",
            "catalogue_sent": False,
            "qr_sent": False,
            "history": [],
            "pending_amount": 0,
            "reminder_count": 0,
        }
        BUSINESS_METRICS["active_leads"] += 1
        save_crm_data()
    return USER_STATES[chat_id]


# ─── Reminder System ──────────────────────────────────────────────────────────
async def send_reminder(chat_id):
    await asyncio.sleep(900)  
    state = USER_STATES.get(chat_id)
    if not state:
        return
    if state.get("qr_sent") and state.get("current_stage") != "payment_confirmed":
        count = state.get("reminder_count", 0)
        if count < len(REMINDER_MESSAGES):
            msg = REMINDER_MESSAGES[count]
            state["reminder_count"] = count + 1
            try:
                await client.send_message(chat_id, msg)
                task = asyncio.create_task(send_reminder_delayed(chat_id, 86400)) 
                REMINDER_TASKS[chat_id] = task
            except Exception:
                pass

async def send_reminder_delayed(chat_id, delay):
    await asyncio.sleep(delay)
    await send_reminder(chat_id)

def cancel_reminder(chat_id):
    if chat_id in REMINDER_TASKS:
        REMINDER_TASKS[chat_id].cancel()
        del REMINDER_TASKS[chat_id]


# ─── Payment & Theme Image Verification ───────────────────────────────────────
async def confirm_payment(chat_id, admin_msg_id):
    if admin_msg_id in PENDING_VERIFICATIONS:
        del PENDING_VERIFICATIONS[admin_msg_id]
    
    state = USER_STATES.get(chat_id)
    if state:
        state["current_stage"] = "payment_confirmed"
        cancel_reminder(chat_id)
        
        amount_closed = state.get("pending_amount", 0)
        BUSINESS_METRICS["total_revenue_inr"] += amount_closed
        BUSINESS_METRICS["pipeline_value_inr"] = max(0, BUSINESS_METRICS["pipeline_value_inr"] - amount_closed)
        BUSINESS_METRICS["closed_won"] += 1
        BUSINESS_METRICS["active_leads"] = max(0, BUSINESS_METRICS["active_leads"] - 1)
        save_crm_data()

    try:
        await client.send_message(chat_id, "Great news! Your payment has been confirmed successfully ✅")
        await asyncio.sleep(1)
        await client.send_message(chat_id, TERMS_MESSAGE)
    except Exception:
        pass

async def auto_confirm_payment(chat_id, admin_msg_id):
    await asyncio.sleep(900)
    if admin_msg_id in PENDING_VERIFICATIONS:
        await confirm_payment(chat_id, admin_msg_id)

async def reject_payment(chat_id, admin_msg_id):
    if admin_msg_id in PENDING_VERIFICATIONS:
        del PENDING_VERIFICATIONS[admin_msg_id]
    try:
        await client.send_message(chat_id, "We were unable to verify your payment screenshot. Could you please send a clearer image? 😊")
    except Exception:
        pass

async def handle_payment_screenshot(event, chat_id, state):
    await humanizer.wait_before_acting("screenshot received")
    await client.send_message(chat_id, "Thank you! We have received your payment screenshot and are verifying it now. Please hold on for a moment 😊")

    try:
        amount = state.get("pending_amount", 0)
        if ADMIN_IDS:
            first_msg_id = None
            for aid in ADMIN_IDS:
                await client.forward_messages(aid, event.message, chat_id)
                buttons = [[
                    Button.inline(f"✅ Confirm ₹{amount}", f"confirm_{chat_id}".encode()),
                    Button.inline("❌ Reject", f"reject_{chat_id}".encode())
                ]]
                fwd_msg = await client.send_message(
                    aid,
                    f"💰 New Booking Advance Screenshot\nCustomer ID: {chat_id}\nExpected Amount: ₹{amount}\n\nPlease verify and tap a button:",
                    buttons=buttons
                )
                if first_msg_id is None:
                    first_msg_id = fwd_msg.id
                    PENDING_VERIFICATIONS[fwd_msg.id] = chat_id

            asyncio.create_task(auto_confirm_payment(chat_id, first_msg_id))
        else:
            await asyncio.sleep(3)
            await confirm_payment(chat_id, -1)
    except Exception:
        pass

async def handle_reference_image(event, chat_id, state):
    await humanizer.wait_before_acting("photo received")
    await client.send_message(chat_id, "This looks incredible! 🎨 I have saved this reference to your event file and shared it directly with our design team.")
    
    try:
        if ADMIN_IDS:
            for aid in ADMIN_IDS:
                await client.forward_messages(aid, event.message, chat_id)
                buttons = [[
                    Button.inline("✅ Acknowledge Theme", f"ack_theme_{chat_id}".encode())
                ]]
                await client.send_message(
                    aid,
                    f"📸 New Theme Reference Photo\nCustomer ID: {chat_id}\n\nPlease review the customer's design inspiration:",
                    buttons=buttons
                )
    except Exception:
        pass


# ─── Admin Button Handler ─────────────────────────────────────────────────────
@client.on(events.CallbackQuery())
async def handle_button_click(event):
    data = event.data.decode()
    if data.startswith("confirm_"):
        customer_id = int(data.split("_")[1])
        await event.answer("✅ Payment Confirmed! Revenue updated.")
        await event.edit("✅ Payment has been confirmed.")
        await confirm_payment(customer_id, event.message_id)
    elif data.startswith("reject_"):
        customer_id = int(data.split("_")[1])
        await event.answer("❌ Payment Rejected!")
        await event.edit("❌ Payment has been rejected.")
        await reject_payment(customer_id, event.message_id)
    elif data.startswith("ack_theme_"):
        await event.answer("✅ Theme Acknowledged!")
        await event.edit("✅ Theme reference has been reviewed and acknowledged.")


# ─── Main Message Handler ─────────────────────────────────────────────────────
@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    if not event.is_private:
        return

    # 🛠️ CRITICAL FIX: Force Telethon to cache the sender entity immediately
    sender = await event.get_sender()
    if not sender:
        return

    chat_id   = event.chat_id
    sender_id = event.sender_id
    user_text = event.text

    if ADMIN_IDS and sender_id in ADMIN_IDS:
        if user_text.strip() == "/report":
            report_msg = (
                "📊 **Live Business Dashboard**\n\n"
                f"💰 **Total Revenue:** ₹{BUSINESS_METRICS['total_revenue_inr']:,}\n"
                f"⏳ **Pipeline Value:** ₹{BUSINESS_METRICS['pipeline_value_inr']:,}\n"
                f"🤝 **Deals Closed:** {BUSINESS_METRICS['closed_won']}\n"
                f"🔥 **Active Leads:** {BUSINESS_METRICS['active_leads']}\n"
            )
            await event.reply(report_msg)
        return

    cancel_reminder(chat_id)
    state = get_state(chat_id)

    # 📸 Distinguish between a Payment Screenshot and a Theme Idea Upload
    if event.photo:
        if state.get("qr_sent") and state.get("current_stage") != "payment_confirmed":
            await handle_payment_screenshot(event, chat_id, state)
        else:
            await handle_reference_image(event, chat_id, state)
        return

    if not user_text or not user_text.strip():
        return

    print(f"\n📩 [Lead {chat_id}]: '{user_text}'")

    current_stage  = state["current_stage"]
    personality    = state["personality"]
    catalogue_sent = state["catalogue_sent"]
    history        = state["history"]

    try:
        await humanizer.wait_before_acting(user_text)

        decision = await brain.analyze_message(
            user_message=user_text,
            current_stage=current_stage,
            personality=personality,
            rate_card_sent=catalogue_sent,
            history=history
        )

        detected_intent  = decision.get("intent", "unknown")
        event_type       = decision.get("event_type", "bday") 
        google_query     = decision.get("google_image_search_query", "")
        reply_text       = decision.get("text", "")
        send_catalogue   = decision.get("send_rate_card", False)
        send_qr          = decision.get("send_qr", False)
        send_trust       = decision.get("send_trust_proof", False)

        state["history"].append({"role": "user", "content": user_text})
        if reply_text:
            state["history"].append({"role": "assistant", "content": reply_text})
        if len(state["history"]) > 20:
            state["history"] = state["history"][-20:]

        if detected_intent in ["pricing", "trust_issue", "payment_ready", "negotiating"]:
            state["current_stage"] = detected_intent

        # 💰 Track Pipeline dynamically based on AI detection
        ai_amount = decision.get("pending_amount", 0)
        if ai_amount > 0:
            if state["pending_amount"] == 0:
                BUSINESS_METRICS["pipeline_value_inr"] += ai_amount
                save_crm_data()
            elif state["pending_amount"] != ai_amount:
                # Adjust if they upgraded/downgraded packages
                BUSINESS_METRICS["pipeline_value_inr"] -= state["pending_amount"]
                BUSINESS_METRICS["pipeline_value_inr"] += ai_amount
                save_crm_data()
            state["pending_amount"] = ai_amount

        typing_duration = min(len(reply_text) * 0.05, 8.0)
        await humanizer.simulate_typing(client, chat_id, duration=typing_duration)

        if reply_text:
            final_text = humanizer.inject_human_typos(reply_text)
            await client.send_message(chat_id, final_text, parse_mode='md')

        # 🔍 GOOGLE IMAGE SEARCH INSPIRATION 🔍
        if google_query and google_query.lower() not in ["none", "false", "", "null", "no"]:
            await humanizer.simulate_typing(client, chat_id, duration=2.0)
            encoded_query = urllib.parse.quote(google_query)
            search_url = f"https://www.google.com/search?tbm=isch&q={encoded_query}"
            
            link_text = f"✨ [Click here to view a curated inspiration board for '{google_query}' on Google Images!]({search_url})"
            try:
                await client.send_message(chat_id, link_text, parse_mode='md', link_preview=True)
            except Exception as e:
                print(f"⚠️ Failed to send google link: {e}")

        elif send_trust and not google_query:
            await asyncio.sleep(1.0)
            pics = get_trust_pics(category=event_type, count=3) 
            if pics:
                for pic in pics:
                    await client.send_file(chat_id, pic)
                    await asyncio.sleep(0.5)

        if send_catalogue and not state["catalogue_sent"]:
            await asyncio.sleep(1.0)
            if os.path.exists(CATALOGUE_PATH):
                await client.send_file(chat_id, CATALOGUE_PATH, caption="Here is our event planning brochure 📋")
                state["catalogue_sent"] = True
            else:
                await client.send_message(chat_id, CATALOGUE_TEXT)
                state["catalogue_sent"] = True

        if send_qr and not state["qr_sent"]:
            await asyncio.sleep(1.0)
            if os.path.exists(QR_CODE_PATH):
                await client.send_file(chat_id, QR_CODE_PATH, caption="Please scan the QR code to lock in your date securely 💳 Once done, kindly send a screenshot for confirmation.")
                state["qr_sent"] = True
                state["current_stage"] = "payment_ready"
                task = asyncio.create_task(send_reminder(chat_id))
                REMINDER_TASKS[chat_id] = task

    except Exception as e:
        print(f"❌ Error handling message from {chat_id}: {e}")

# ─── Entry Point ──────────────────────────────────────────────────────────────
async def main():
    global ADMIN_IDS
    print("=" * 50)
    print("  Event Management CRM & Sales Bot — Starting Up")
    print("=" * 50)
    
    await client.start()
    me = await client.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")

    for username in ADMIN_USERNAMES:
        try:
            admin = await client.get_entity(username)
            ADMIN_IDS.append(admin.id)
            print(f"✅ Admin registered: {username}")
        except Exception:
            print(f"⚠️  Could not resolve admin {username}")

    print("\n👂 Bot is live — capturing leads and driving revenue...\n")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())