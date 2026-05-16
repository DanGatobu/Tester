import requests
import time

BASE_URL = "http://127.0.0.1:5000"
PHONE = "+254711223344"
SESSION_ID = f"AT_Session_{int(time.time())}"

print("📞 Simulating incoming call from AT...")
resp1 = requests.post(f"{BASE_URL}/voice/answer", data={
    "sessionId": SESSION_ID,
    "callerNumber": PHONE,
    "direction": "Inbound"
})
print("AT Response (XML):")
print(resp1.text)
print("-" * 50)

time.sleep(1)

print("📲 Simulating caller pressing '1' (Employer)...")
resp2 = requests.post(f"{BASE_URL}/voice/ivr", data={
    "sessionId": SESSION_ID,
    "callerNumber": PHONE,
    "dtmfDigits": "1"
})
print("AT Response (XML):")
print(resp2.text)
print("-" * 50)

time.sleep(1)

print("🎙️  Simulating AT sending the recorded audio URL...")
# A working public audio file (Apollo 13: "Houston we've had a problem here")
AUDIO_URL = "http://127.0.0.1:5000/dummy_audio"

resp3 = requests.post(f"{BASE_URL}/voice/recording", data={
    "sessionId": SESSION_ID,
    "callerNumber": PHONE,
    "duration": "5",
    "recordingUrl": AUDIO_URL
})
print("AT Final Response (XML):")
print(resp3.text)
print("-" * 50)
print("✅ Test Complete! Check your Dashboard to see the new caller.")
