Echo/AI - Mesh Network AI Assistant
A Reticulum-based LXMF application that provides AI-powered assistance over mesh networks. Echo/AI integrates with Google's Gemini AI to deliver intelligent responses while handling telemetry and network data from connected devices.

https://img.shields.io/badge/Network-Reticulum-blue
https://img.shields.io/badge/Protocol-LXMF-green
https://img.shields.io/badge/Python-3.7+-yellow

🌟 Features
Mesh Network Communication: Built on Reticulum for decentralized, resilient networking

AI-Powered Responses: Integrates with Google Gemini for intelligent conversations

Telemetry Support: Automatically processes and interprets sensor data

Network Analytics: Provides insights about mesh network performance and topology

Cross-Platform: Runs anywhere Python and Reticulum are supported

Privacy-Focused: Your data stays on your network

Easy Deployment: Simple setup and configuration

📋 Requirements
Python 3.7+

Reticulum

LXMF

Google Gemini API key

🚀 Installation
Install dependencies:

bash
pip install rns lxmf google-generativeai
Clone this repository:

bash
git clone https://github.com/yourusername/echo-ai.git
cd echo-ai
Set up your environment:

bash
export GEMINI_API_KEY="your_google_api_key_here"
Run the application:

bash
python echo_ai.py
⚙️ Configuration
Echo/AI uses a simple configuration system. Key settings can be modified in the script:

python
CONFIG = {
    "config_dir": os.path.expanduser("~/.nomadmb"),
    "display_name": "Echo/AI", 
    "announce_interval": 1800,  # 30 minutes
    "model_name": "gemini-2.5-flash"
}
📡 How It Works
Message Flow
Receive Message: Listens for LXMF messages on the Reticulum network

Process Telemetry: Automatically decodes binary telemetry data (GPS, sensors, etc.)

Analyze Network: Examines network statistics and topology

AI Analysis: Sends message with context to Gemini AI

Send Response: Returns intelligent response to the sender

Supported Telemetry
GPS coordinates (decoded from scaled integer format)

Battery status and temperature

Acceleration and motion data

Environmental sensors (light, proximity)

Magnetic field readings

Network transport statistics

Network Data Analysis
Echo/AI can provide insights about:

Network connectivity and node relationships

Signal strength and link quality

Data throughput and performance

Network topology and routing paths

Interface status (LoRa, WiFi, Ethernet, etc.)

🔧 Usage
Basic Operation
Once running, Echo/AI will:

Announce its presence on the network every 30 minutes

Listen for incoming LXMF messages

Automatically respond to any received messages

Process attached telemetry and network data for context-aware responses

Sending Messages
Use any LXMF-compatible client to send messages to Echo/AI's destination hash (shown in logs on startup).

Example Interactions
Location & Sensor Data
text
You: "What's my current location and battery status?"

Echo/AI: "Based on your telemetry data, you're currently at 
latitude 40.7128, longitude -74.0060 (New York City area). 
Your battery is at 85% charge and not currently charging."
Network Analysis
text
You: "How's my network connection looking?"

Echo/AI: "Your network stats show excellent connectivity:
• Connected to 8 nodes in the mesh
• Strong signal to nearest hop (-45 dBm)
• Data throughput: 128 kbps stable
• Using LoRa and WiFi interfaces
• Network latency: 120ms average

Your device is acting as a relay for 3 other nodes."
Emergency Scenario
text
You: "I've fallen and my accelerometer shows sudden impact. What's my network situation?"

Echo/AI: "⚠️ I detect an emergency situation! Your sensors show:
• Sudden high-G impact detected
• Current location: 34.0522°N, 118.2437°W (Los Angeles)
• Battery: 72% - sufficient for communications
• Network: Strong mesh with 12 nodes, 3 hops to emergency services gateway
• Recommended: Send emergency alert via the 'help' node that has satellite backup"
Field Research
text
You: "Analyze my sensor readings and network coverage for this research area"

Echo/AI: "Research Site Analysis:
Environmental:
• Temperature: 22.3°C, Light: 1250 lux
• Stable magnetic field readings
• 4 hours of motion data collected

Network Coverage:
• Mesh spans 2.3km diameter area
• 15 research nodes online
• Data sync: 98% complete
• Weak spot detected NE of your position - consider deploying relay node"
🛠️ Development
Project Structure
text
echo-ai/
├── echo_ai.py          # Main application
├── README.md           # This file
└── requirements.txt    # Python dependencies
Key Components
EchoAIApplication: Main application class

decode_telemetry_data(): Handles binary telemetry decoding

ai_chatbot_reply(): Interfaces with Gemini AI

handle_incoming(): Processes incoming messages

Network Data Structure
Echo/AI processes Reticulum transport data (key 25) containing:

json
{
  "rns_transport": {
    "interfaces": [
      {
        "name": "LoRa",
        "status": "active",
        "peers": 5,
        "throughput": 12500
      }
    ],
    "hops": 3,
    "latency": 150,
    "connected_nodes": ["node1", "node2", "node3"]
  }
}
Extending Functionality
Add new telemetry types: Extend the decode_telemetry_data() method

Custom AI behavior: Modify the system prompt in ai_chatbot_reply()

Additional protocols: Add new message handlers alongside LXMF

Network monitoring: Enhance with real-time topology analysis

🔒 Privacy & Security
No data is stored permanently

All communications are encrypted via Reticulum

API calls to Google are transient and not stored

You control the network and data flow

Network topology data never leaves your mesh

🌍 Use Cases
Field Research: AI-assisted data analysis in remote locations

Emergency Response: Intelligent coordination without infrastructure

IoT Networks: Smart sensor interpretation and alerts

Network Operations: Real-time mesh network monitoring and optimization

Educational Tools: Mesh networking and AI demonstrations

Digital Nomads: Off-grid intelligent assistance

Community Networks: Neighborhood-scale mesh monitoring
