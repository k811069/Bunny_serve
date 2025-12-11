import logging
import asyncio
import os
import json
import yaml
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    AgentSession,
    Agent,
    RunContext,
)
from livekit.agents.llm import function_tool
from livekit import rtc
from livekit.plugins import elevenlabs, groq, silero

# Import music service and unified audio player
from src.services.music_service import MusicService
from src.services.unified_audio_player import UnifiedAudioPlayer

# Load environment variables first
load_dotenv(".env")

logger = logging.getLogger("agent")

# Load configuration from config.yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# Select prompt based on ACTIVE_PROMPT in .env (1-4)
# Falls back to default_prompt if not set or invalid
def get_active_prompt():
    active_prompt_num = os.getenv("ACTIVE_PROMPT", "1")
    try:
        prompt_num = int(active_prompt_num)
        if 1 <= prompt_num <= 4:
            prompts = config.get("prompts", {})
            prompt_key = f"prompt{prompt_num}"
            prompt = prompts.get(prompt_key)
            if prompt:
                logger.info(f"Using prompt{prompt_num} from config.yaml")
                return prompt
            else:
                logger.warning(f"prompt{prompt_num} not found in config.yaml, using default_prompt")
        else:
            logger.warning(f"ACTIVE_PROMPT={prompt_num} out of range (1-4), using default_prompt")
    except ValueError:
        logger.warning(f"Invalid ACTIVE_PROMPT value '{active_prompt_num}', using default_prompt")

    return config.get("default_prompt", "You are a helpful voice assistant.")

AGENT_PROMPT = get_active_prompt()

# ElevenLabs configuration from environment variables
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "ODq5zmih8GrVes37Dizd")
ELEVENLABS_TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")

# Groq LLM configuration from environment variables
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.6"))

# Initialize music service and audio player globally
music_service = MusicService()
unified_audio_player = UnifiedAudioPlayer()


class MusicPlayerAgent(Agent):
    """Voice agent with music playback capabilities"""

    def __init__(self, instructions: str, music_svc: MusicService, audio_player: UnifiedAudioPlayer):
        super().__init__(instructions=instructions)
        self.music_service = music_svc
        self.audio_player = audio_player

    @function_tool
    async def play_music(self, context: RunContext, song_name: str, language: str = None):
        """
        Search and play a song by name. Use this when the user asks to play music or a specific song.

        Args:
            song_name: The name of the song to search for and play
            language: Optional language filter (e.g., 'English', 'Hindi', 'Telugu')
        """
        logger.info(f"🎵 [MUSIC TOOL] Playing music: '{song_name}', language: {language}")

        try:
            # Search for the song
            results = await self.music_service.search_songs(song_name, language)

            if not results:
                logger.warning(f"🎵 No songs found for '{song_name}'")
                return None, f"I couldn't find a song matching '{song_name}'. Try a different name or check the spelling."

            # Get the best match
            best_match = results[0]
            song_title = best_match['title']
            song_url = best_match['url']

            logger.info(f"🎵 Found song: '{song_title}' - URL: {song_url}")

            # Play through unified audio player (streams through agent's TTS channel)
            await self.audio_player.play_from_url(song_url, song_title)

            logger.info(f"🎵 Started playing: {song_title}")
            # Return empty string to avoid TTS speaking over the music
            return None, ""

        except Exception as e:
            logger.error(f"🎵 Error playing music: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None, f"Sorry, I had trouble playing that song. Please try again."

    @function_tool
    async def stop_music(self, context: RunContext):
        """
        Stop the currently playing music. Use this when the user asks to stop or pause music.
        """
        logger.info("🎵 [MUSIC TOOL] Stopping music")

        try:
            await self.audio_player.stop()
            logger.info("🎵 Music stopped")
            return None, "Music stopped."

        except Exception as e:
            logger.error(f"🎵 Error stopping music: {e}")
            return None, "Sorry, I had trouble stopping the music."

    @function_tool
    async def play_random_music(self, context: RunContext, language: str = None):
        """
        Play a random song. Use this when the user asks to play any song or random music.

        Args:
            language: Optional language filter (e.g., 'English', 'Hindi', 'Telugu')
        """
        logger.info(f"🎵 [MUSIC TOOL] Playing random music, language: {language}")

        try:
            result = await self.music_service.get_random_song(language)

            if not result:
                return None, "Sorry, I couldn't find any songs to play."

            song_title = result['title']
            song_url = result['url']

            logger.info(f"🎵 Random song: '{song_title}'")

            # Play through unified audio player
            await self.audio_player.play_from_url(song_url, song_title)

            # Return empty string to avoid TTS speaking over the music
            return None, ""

        except Exception as e:
            logger.error(f"🎵 Error playing random music: {e}")
            return None, "Sorry, I had trouble playing a random song."


async def entrypoint(ctx: JobContext):
    """Voice agent using ElevenLabs STT/TTS and Groq LLM"""

    logger.info(f"Starting agent in room: {ctx.room.name}")

    # Initialize music service
    logger.info("Initializing music service...")
    await music_service.initialize()
    logger.info("Music service initialized")

    # Extract MAC address from room name (format: UUID_MAC)
    device_mac = None
    room_name = ctx.room.name
    if "_" in room_name:
        parts = room_name.split("_")
        if len(parts) >= 2:
            mac_part = parts[-1]
            if len(mac_part) == 12 and mac_part.isalnum():
                device_mac = ":".join(mac_part[i : i + 2] for i in range(0, 12, 2))
                logger.info(f"Device MAC: {device_mac}")

    # Use prompt from config.yaml
    agent_prompt = AGENT_PROMPT

    # Initialize models
    logger.info("Initializing ElevenLabs STT (scribe_v2_realtime)...")
    logger.info(f"Initializing ElevenLabs TTS (model: {ELEVENLABS_TTS_MODEL}, voice: {ELEVENLABS_VOICE_ID})...")
    logger.info(f"Initializing Groq LLM (model: {GROQ_MODEL})...")

    # Check if Push-to-Talk mode is enabled
    ptt_mode = os.getenv("PTT_MODE", "auto").lower() == "manual"
    logger.info(f"PTT Mode: {ptt_mode}")

    # Create ElevenLabs STT with streaming (scribe_v2_realtime model)
    stt = elevenlabs.STT(use_realtime=True)

    # Create ElevenLabs TTS
    tts = elevenlabs.TTS(
        voice_id=ELEVENLABS_VOICE_ID,
        model=ELEVENLABS_TTS_MODEL,
    )

    # Create Groq LLM
    llm = groq.LLM(
        model=GROQ_MODEL,
        temperature=GROQ_TEMPERATURE,
    )

    # Create Silero VAD for voice activity detection
    vad = silero.VAD.load(
        min_speech_duration=0.05,
        min_silence_duration=0.55 if not ptt_mode else 1.0,  # Longer silence for PTT
        activation_threshold=0.5,
    )

    # Create AgentSession with appropriate turn detection mode
    if ptt_mode:
        session = AgentSession(
            stt=stt,
            tts=tts,
            llm=llm,
            vad=vad,
            turn_detection="manual",
        )
        logger.info("[PTT] AgentSession created with turn_detection='manual'")
    else:
        session = AgentSession(
            stt=stt,
            tts=tts,
            llm=llm,
            vad=vad,
        )
        logger.info("[AUTO] AgentSession created with automatic turn detection")

    # ============================================================================
    # STATE MANAGEMENT
    # ============================================================================

    current_state = "idle"
    last_state_change_time = 0.0
    STATE_DEBOUNCE_MS = 350  # Minimum time between state changes to prevent LED flickering

    async def emit_agent_state(old_state: str, new_state: str):
        """Emit agent state via data channel for MQTT gateway"""
        nonlocal current_state, last_state_change_time
        import time

        try:
            # Debounce: prevent rapid state changes from causing LED flickering
            current_time = time.time() * 1000  # Convert to ms
            if current_time - last_state_change_time < STATE_DEBOUNCE_MS:
                logger.debug(f"State change debounced: {old_state} -> {new_state} (too fast)")
                return

            current_state = new_state
            last_state_change_time = current_time

            payload = json.dumps(
                {
                    "type": "agent_state_changed",
                    "data": {"old_state": old_state, "new_state": new_state},
                }
            )

            await ctx.room.local_participant.publish_data(
                payload.encode("utf-8"), reliable=True
            )
            logger.info(f"State emitted: {old_state} -> {new_state}")
        except Exception as e:
            logger.error(f"Failed to emit state: {e}")

    async def emit_speech_created(text: str = ""):
        """Emit speech_created event via data channel - triggers TTS start in MQTT gateway"""
        try:
            payload = json.dumps(
                {
                    "type": "speech_created",
                    "data": {"text": text},
                }
            )

            await ctx.room.local_participant.publish_data(
                payload.encode("utf-8"), reliable=True
            )
            logger.info("speech_created event emitted")
        except Exception as e:
            logger.error(f"Failed to emit speech_created: {e}")

    # Hook into user_input_transcribed to log when user speaks
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev):
        """Log user transcripts (only final ones)"""
        try:
            # Skip partial transcripts
            if hasattr(ev, 'is_final') and not ev.is_final:
                return

            transcript = getattr(ev, 'transcript', None) or getattr(ev, 'text', None) or str(ev)
            logger.info(f"User said: {transcript}")

            # Emit via data channel for gateway
            payload = json.dumps({
                "type": "user_input_transcribed",
                "data": {"transcript": transcript, "is_final": True}
            })
            asyncio.create_task(ctx.room.local_participant.publish_data(
                payload.encode("utf-8"), reliable=True))
        except Exception as e:
            logger.error(f"Error in user_input_transcribed handler: {e}")

    # Hook into agent_state_changed to emit events to gateway
    @session.on("agent_state_changed")
    def on_agent_state_changed_for_tts(ev):
        """Emit agent_state_changed and speech_created to gateway"""
        try:
            # Get old and new state from the event
            old_state = getattr(ev, 'old_state', None)
            new_state = getattr(ev, 'new_state', None)

            # Convert state objects to strings if needed
            old_state_str = str(old_state).lower() if old_state else "unknown"
            new_state_str = str(new_state).lower() if new_state else "unknown"

            logger.info(f"EVENT: agent_state_changed - {old_state_str} -> {new_state_str}")

            # Always emit agent_state_changed to gateway (it handles TTS stop)
            asyncio.create_task(emit_agent_state(old_state_str, new_state_str))

            # When transitioning TO speaking, also emit speech_created for TTS start
            if 'speaking' in new_state_str and 'speaking' not in old_state_str:
                logger.info(f"Emitting speech_created (state: {old_state_str} -> {new_state_str})")
                asyncio.create_task(emit_speech_created())

        except Exception as e:
            logger.error(f"Error in agent_state_changed handler: {e}")

    # ============================================================================
    # PARTICIPANT TRACKING & CLEANUP
    # ============================================================================

    participant_count = len(ctx.room.remote_participants)
    cleanup_completed = False

    async def cleanup_session():
        """Minimal cleanup on disconnect"""
        nonlocal cleanup_completed
        if cleanup_completed:
            return
        cleanup_completed = True

        logger.info("Cleaning up session...")

        try:
            if ctx.room and hasattr(ctx.room, "disconnect"):
                await ctx.room.disconnect()
        except Exception as e:
            logger.warning(f"Disconnect error: {e}")

        logger.info("Cleanup complete")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        nonlocal participant_count
        participant_count -= 1
        logger.info(f"Participant left: {participant.identity}, remaining: {participant_count}")
        if participant_count == 0:
            asyncio.create_task(cleanup_session())

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        nonlocal participant_count
        participant_count += 1
        logger.info(f"Participant joined: {participant.identity}, total: {participant_count}")

    @ctx.room.on("disconnected")
    def on_room_disconnected():
        logger.info("Room disconnected")
        asyncio.create_task(cleanup_session())

    # ============================================================================
    # DATA CHANNEL HANDLERS
    # ============================================================================

    @ctx.room.on("data_received")
    def on_data_received(packet: rtc.DataPacket):
        try:
            payload = packet.data.decode('utf-8')
            data = json.loads(payload)
            logger.debug(f"Received: {data.get('type')}")

            if data.get("type") in ["start_greeting", "agent_ready"]:
                logger.info("Greeting request received")
                asyncio.create_task(trigger_greeting())
            elif data.get("type") == "end_prompt":
                logger.info("End prompt received, will disconnect naturally")
            elif data.get("type") == "abort_playback":
                logger.info("Abort signal received - interrupting agent")
                try:
                    session.interrupt()
                    logger.info("Agent interrupted successfully")
                except Exception as abort_error:
                    logger.error(f"Failed to interrupt agent: {abort_error}")

        except Exception as e:
            logger.warning(f"Failed to handle data: {e}")

    async def trigger_greeting():
        """Generate initial greeting"""
        await asyncio.sleep(2.0)  # Brief delay for session stability
        try:
            logger.info("Generating greeting...")

            result = await session.generate_reply(
                instructions="Say hello and introduce yourself as a funny goofy friend."
            )

            logger.info(f"Generate reply result: {result}")
            logger.info("Greeting sent")
        except Exception as e:
            logger.error(f"Greeting error: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

    # ============================================================================
    # START SESSION
    # ============================================================================

    # Connect to room first
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for a participant to join
    participant = await ctx.wait_for_participant()
    logger.info(f"Participant joined: {participant.identity}")

    # Set up unified audio player with session and context
    unified_audio_player.set_session(session)
    unified_audio_player.set_context(ctx)
    logger.info("Unified audio player configured with session and context")

    # Start session with the room and agent instructions (with music tools)
    await session.start(
        room=ctx.room,
        agent=MusicPlayerAgent(
            instructions=agent_prompt,
            music_svc=music_service,
            audio_player=unified_audio_player
        ),
    )

    logger.info(f"Voice agent is LIVE! (ElevenLabs STT/TTS + Groq LLM)")
    logger.info(f"Agent prompt: {agent_prompt[:100]}...")

    # ============================================================================
    # PUSH-TO-TALK RPC METHODS
    # ============================================================================

    if ptt_mode:
        try:
            session.input.set_audio_enabled(False)
            logger.info("[PTT] Audio input disabled by default - waiting for start_turn RPC")
        except Exception as e:
            logger.warning(f"[PTT] Could not disable audio input: {e}")

    @ctx.room.local_participant.register_rpc_method("start_turn")
    async def start_turn(data: rtc.RpcInvocationData):
        """Handle PTT start - enable audio input and prepare for user speech"""
        logger.info("[PTT] start_turn RPC received - enabling audio input")
        try:
            if hasattr(session, 'interrupt'):
                session.interrupt()
                logger.info("[PTT] Interrupted current speech")

            if hasattr(session, 'clear_user_turn'):
                session.clear_user_turn()
                logger.info("[PTT] Cleared user turn")

            if hasattr(session, 'input') and hasattr(session.input, 'set_audio_enabled'):
                session.input.set_audio_enabled(True)
                logger.info("[PTT] Audio input enabled, ready to receive speech")
            else:
                logger.warning("[PTT] session.input.set_audio_enabled not available")

            return "ok"
        except Exception as e:
            logger.error(f"[PTT] start_turn failed: {e}")
            import traceback
            logger.error(f"[PTT] Traceback: {traceback.format_exc()}")
            return f"error: {e}"

    @ctx.room.local_participant.register_rpc_method("end_turn")
    async def end_turn(data: rtc.RpcInvocationData):
        """Handle PTT end - let VAD detect silence and respond naturally."""
        logger.info("[PTT] end_turn RPC received - letting VAD handle turn end")
        try:
            logger.info("[PTT] Waiting for VAD to detect silence...")

            async def delayed_disable():
                await asyncio.sleep(3.0)
                if hasattr(session, 'input') and hasattr(session.input, 'set_audio_enabled'):
                    session.input.set_audio_enabled(False)
                    logger.info("[PTT] Audio input disabled after delay")

            asyncio.create_task(delayed_disable())

            return "ok"
        except Exception as e:
            logger.error(f"[PTT] end_turn failed: {e}")
            import traceback
            logger.error(f"[PTT] Traceback: {traceback.format_exc()}")
            return f"error: {e}"

    @ctx.room.local_participant.register_rpc_method("cancel_turn")
    async def cancel_turn(data: rtc.RpcInvocationData):
        """Handle PTT cancel - disable audio and discard user turn"""
        logger.info("[PTT] cancel_turn RPC received - canceling turn")
        try:
            if hasattr(session, 'input') and hasattr(session.input, 'set_audio_enabled'):
                session.input.set_audio_enabled(False)
            if hasattr(session, 'clear_user_turn'):
                session.clear_user_turn()
            logger.info("[PTT] Turn canceled")
            return "ok"
        except Exception as e:
            logger.error(f"[PTT] cancel_turn failed: {e}")
            import traceback
            logger.error(f"[PTT] Traceback: {traceback.format_exc()}")
            return f"error: {e}"

    logger.info("[PTT] Push-to-talk RPC methods registered")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )
