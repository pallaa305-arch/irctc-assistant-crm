import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  Train, 
  Radio, 
  IndianRupee, 
  CheckCircle2, 
  Clock, 
  AlertCircle,
  RefreshCw,
  MessageSquare
} from 'lucide-react';
import TrainResultsCard from '../components/chat/TrainResultsCard';
import FareBreakdownCard from '../components/chat/FareBreakdownCard';
import LivePaymentQRModal from '../components/chat/LivePaymentQRModal';
import CaptchaFallbackDrawer from '../components/chat/CaptchaFallbackDrawer';
import LiveAutomationTimeline from '../components/chat/LiveAutomationTimeline';

export default function AIAssistant({ setTab }) {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [automationLogs, setAutomationLogs] = useState([]);
  const [currentStage, setCurrentStage] = useState('IDLE');
  
  // Modals & Drawers
  const [qrModalData, setQrModalData] = useState(null);
  const [captchaData, setCaptchaData] = useState(null);

  // Persistent Session ID
  const [sessionId] = useState(() => {
    let sid = localStorage.getItem('irctc_ai_session_id');
    if (!sid) {
      sid = 'web_' + Math.random().toString(36).substring(2, 10);
      localStorage.setItem('irctc_ai_session_id', sid);
    }
    return sid;
  });

  const wsRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Load chat history on mount
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`/api/chat/history/${sessionId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.history && data.history.length > 0) {
            setMessages(data.history.map(m => ({
              id: Math.random().toString(),
              role: m.role,
              text: m.content
            })));
          } else {
            // Initial Welcome Message
            setMessages([{
              id: 'welcome_1',
              role: 'assistant',
              text: "👋 **Namaste! Main aapka AI IRCTC Booking Assistant hoon.**\n\nAap mujhse natural Hinglish ya English me trains search, availability check, dynamic fare calculation, ya direct booking karwa sakte hain.\n\nNiche diye gaye suggestions par click karein ya apna message likhein!"
            }]);
          }
        }
      } catch (err) {
        console.warn('History fetch error:', err);
      }
    };
    fetchHistory();
  }, [sessionId]);

  // Establish WebSocket Connection for Real-Time Event Bus
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.port === '5173' ? '127.0.0.1:8000' : window.location.host;
    const wsUrl = `${protocol}//${host}/ws/chat/${sessionId}`;

    const connectWs = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const type = payload.type;
          const data = payload.data;

          if (type === 'STAGE_UPDATE') {
            setCurrentStage(data.stage || 'PROCESSING');
            if (data.message) {
              setAutomationLogs(prev => [...prev, data.message]);
            }
          } else if (type === 'TRAINS_FOUND') {
            setCurrentStage('SELECTING_TRAIN');
            setAutomationLogs(prev => [...prev, `Found ${data.trains_count || data.trains?.length} trains on IRCTC`]);
          } else if (type === 'PAYMENT_QR_READY') {
            setCurrentStage('PAYMENT_PENDING');
            setQrModalData(data);
          } else if (type === 'CAPTCHA_REQUIRED') {
            setCaptchaData(data);
          } else if (type === 'RESPONSE') {
            setIsLoading(false);
            setMessages(prev => [...prev, {
              id: Math.random().toString(),
              role: 'assistant',
              text: data.text,
              action_type: data.action_type,
              payload: data.payload
            }]);
          }
        } catch (e) {
          console.error('Error parsing WS message:', e);
        }
      };

      ws.onclose = () => {
        // Retry connection in 3 seconds
        setTimeout(connectWs, 3000);
      };
    };

    connectWs();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend || inputText).trim();
    if (!text || isLoading) return;

    setInputText('');
    const userMsgId = Math.random().toString();
    setMessages(prev => [...prev, { id: userMsgId, role: 'user', text }]);
    setIsLoading(true);

    // If WebSocket is open, send via WS
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: text }));
    } else {
      // REST API Fallback
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
            channel: 'web'
          })
        });
        const data = await res.json();
        setIsLoading(false);
        setMessages(prev => [...prev, {
          id: Math.random().toString(),
          role: 'assistant',
          text: data.text,
          action_type: data.action_type,
          payload: data.payload
        }]);
      } catch (err) {
        setIsLoading(false);
        setMessages(prev => [...prev, {
          id: Math.random().toString(),
          role: 'assistant',
          text: '❌ Assistant se connect karne me dikkat aayi. Kripya backend status check karein.'
        }]);
      }
    }
  };

  const handleSelectClass = (train, cls, avlInfo) => {
    handleSendMessage(`Calculate fare for ${train.train_number} class ${cls} 1 passenger`);
  };

  const handleBookTrain = (train) => {
    handleSendMessage(`Book train ${train.train_number} class 3A`);
  };

  const suggestions = [
    'Delhi se Jammu kal ki train check karo',
    'Check PNR 2451234567',
    'Train 12952 ka live status kya hai',
    'Calculate fare for 12952 class 3A 2 passengers'
  ];

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-8rem)]">
      {/* Left Chat Area */}
      <div className="flex-1 flex flex-col bg-white dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-3xl shadow-sm overflow-hidden">
        {/* Chat Header */}
        <div className="px-6 py-4 border-b border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between bg-zinc-50/50 dark:bg-zinc-900/30">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white flex items-center gap-2">
                IRCTC AI Booking Assistant
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
              </h3>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Unified Multi-Channel Agent (Web & Telegram Parity)
              </p>
            </div>
          </div>

          <div className="text-[11px] font-mono text-zinc-400">
            Session: <span className="text-emerald-500">{sessionId}</span>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-4">
          {messages.map((m) => {
            const isUser = m.role === 'user';

            return (
              <div
                key={m.id}
                className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 mt-0.5">
                    <Sparkles className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-xl rounded-2xl p-4 text-xs leading-relaxed ${
                    isUser
                      ? 'bg-emerald-600 text-white shadow-sm font-medium rounded-br-sm'
                      : 'bg-zinc-100 dark:bg-zinc-900/90 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-800/70 rounded-bl-sm'
                  }`}
                >
                  <div className="whitespace-pre-wrap font-sans">
                    {m.text}
                  </div>

                  {/* Inline Rich Widgets */}
                  {!isUser && m.action_type === 'TRAIN_LIST' && m.payload && (
                    <TrainResultsCard
                      data={m.payload}
                      onSelectClass={handleSelectClass}
                      onBookTrain={handleBookTrain}
                    />
                  )}

                  {!isUser && m.action_type === 'FARE_BREAKDOWN' && m.payload && (
                    <FareBreakdownCard
                      data={m.payload}
                      onConfirmBooking={() => handleSendMessage(`Book ${m.payload.train_number} ${m.payload.travel_class}`)}
                    />
                  )}
                </div>
              </div>
            );
          })}

          {isLoading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                <Sparkles className="w-4 h-4 animate-spin" />
              </div>
              <div className="p-3.5 rounded-2xl bg-zinc-100 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-xs text-zinc-500 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce"></span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce [animation-delay:0.2s]"></span>
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-bounce [animation-delay:0.4s]"></span>
                <span className="ml-1 italic font-medium">IRCTC automation engine reasoning...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Quick Suggestion Pills */}
        <div className="px-4 py-2 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/40 dark:bg-zinc-900/20 flex flex-wrap gap-2 overflow-x-auto">
          {suggestions.map((s, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(s)}
              className="px-2.5 py-1 rounded-full text-[11px] font-medium bg-white dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:border-emerald-500 hover:text-emerald-500 transition-all cursor-pointer shrink-0"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Type in Hinglish or English: 'Delhi se Jammu kal ki train'..."
              className="flex-1 px-4 py-3 rounded-2xl bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-xs text-zinc-900 dark:text-white placeholder-zinc-400 focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button
              type="submit"
              disabled={!inputText.trim() || isLoading}
              className="p-3 rounded-2xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold transition-all shadow-md shadow-emerald-600/20 cursor-pointer shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>

      {/* Right Column: Live Automation Radar */}
      <div className="w-full lg:w-80 shrink-0">
        <LiveAutomationTimeline
          currentStage={currentStage}
          logs={automationLogs}
        />
      </div>

      {/* Live Payment QR Modal */}
      {qrModalData && (
        <LivePaymentQRModal
          qrPath={qrModalData.qr_path}
          qrBase64={qrModalData.qr_base64}
          amount={qrModalData.amount}
          onClose={() => setQrModalData(null)}
          onPaid={() => {
            setQrModalData(null);
            handleSendMessage('I have completed payment');
          }}
        />
      )}

      {/* Live CAPTCHA / OTP Fallback Drawer */}
      {captchaData && (
        <CaptchaFallbackDrawer
          challengeType={captchaData.type || 'CAPTCHA'}
          imageSrc={captchaData.image_url}
          suggestedValue={captchaData.suggested_captcha || captchaData.suggested_value || ''}
          onSubmit={(val) => {
            setCaptchaData(null);
            handleSendMessage(val);
          }}
          onCancel={() => setCaptchaData(null)}
        />
      )}
    </div>
  );
}
