import React, { useState, useRef, useEffect, Component } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Video, VideoOff, Mic, MicOff, Play, Square, 
  ChevronRight, CheckCircle, AlertCircle,
  Clock, Award, MessageSquare, User, BarChart3, RefreshCw
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE = 'http://localhost:8000';

// ===== ERROR BOUNDARY =====
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Interview Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card text-center py-12">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-400 mb-2">Đã xảy ra lỗi</h2>
          <p className="text-slate-400 mb-4">{this.state.error?.message || 'Lỗi không xác định'}</p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            className="btn-primary inline-flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Tải lại trang
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ===== SIMPLE COMPONENTS =====
const LoadingDots = () => (
  <div className="loading-dots">
    <span></span><span></span><span></span>
  </div>
);

const ScoreBadge = ({ score, label }) => {
  const getColor = (s) => {
    if (s >= 8) return 'text-green-400 border-green-500/30 bg-green-500/10';
    if (s >= 6) return 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10';
    return 'text-red-400 border-red-500/30 bg-red-500/10';
  };
  return (
    <div className={`px-3 py-2 rounded-lg border ${getColor(score)}`}>
      <div className="text-2xl font-bold">{score}/10</div>
      <div className="text-xs opacity-70">{label}</div>
    </div>
  );
};

// ===== MAIN COMPONENT =====
function InterviewContent() {
  // Core states
  const [stage, setStage] = useState('setup');
  const [sessionId, setSessionId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [currentEvaluation, setCurrentEvaluation] = useState(null);
  
  // Input mode - default to TEXT (more stable)
  const [useTextMode, setUseTextMode] = useState(true);
  const [textAnswer, setTextAnswer] = useState('');
  
  // Video states
  const [cameraOn, setCameraOn] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [timeLeft, setTimeLeft] = useState(0);
  const [videoRecorded, setVideoRecorded] = useState(false);
  const [capturedFrames, setCapturedFrames] = useState([]); // Multiple frames
  
  // Audio states
  const [audioBlob, setAudioBlob] = useState(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcriptText, setTranscriptText] = useState('');
  
  // CV/JD
  const [cvText, setCvText] = useState('');
  const [jdText, setJdText] = useState('');
  const [cvLoading, setCvLoading] = useState(true);

  // Refs
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const audioStreamRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const mountedRef = useRef(true);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      stopCamera();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Fetch CV/JD
  useEffect(() => {
    const fetchCvJd = async () => {
      try {
        const response = await axios.get(`${API_BASE}/api/get-cv-jd`);
        if (response.data.success && mountedRef.current) {
          setCvText(response.data.cv_text || '');
          setJdText(response.data.jd_text || '');
        }
      } catch (error) {
        console.error('Error fetching CV/JD:', error);
      } finally {
        if (mountedRef.current) setCvLoading(false);
      }
    };
    fetchCvJd();
  }, []);

  // Format time
  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  // Camera controls
  const startCamera = async () => {
    try {
      // Get video stream
      const videoStream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: false // Video only
      });
      streamRef.current = videoStream;
      if (videoRef.current) {
        videoRef.current.srcObject = videoStream;
      }
      
      // Get audio stream separately
      try {
        const audioStream = await navigator.mediaDevices.getUserMedia({
          video: false,
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            sampleRate: 44100
          }
        });
        audioStreamRef.current = audioStream;
        console.log('Audio stream ready');
      } catch (audioErr) {
        console.error('Audio error:', audioErr);
        toast.error('Không thể truy cập microphone');
      }
      
      setCameraOn(true);
      return true;
    } catch (error) {
      console.error('Camera error:', error);
      toast.error('Không thể truy cập camera');
      return false;
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach(track => track.stop());
      audioStreamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCameraOn(false);
    setIsRecording(false);
  };

  // Start interview
  const startInterview = async () => {
    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE}/api/interview/start`, {
        cv_text: cvText,
        jd_text: jdText,
        num_questions: 3
      });

      if (response.data.success && mountedRef.current) {
        setSessionId(response.data.session_id);
        setQuestions(response.data.questions);
        setCurrentQuestionIdx(0);
        setStage('interview');
        toast.success('Bắt đầu phỏng vấn!');
      } else {
        toast.error(response.data.error || 'Lỗi bắt đầu phỏng vấn');
      }
    } catch (error) {
      console.error(error);
      toast.error('Lỗi kết nối server');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  // Submit text answer
  const submitTextAnswer = async () => {
    if (!textAnswer.trim()) {
      toast.error('Vui lòng nhập câu trả lời!');
      return;
    }
    
    const answerToSend = textAnswer.trim();
    console.log('=== Submitting Text Answer ===');
    console.log('Session ID:', sessionId);
    console.log('Answer:', answerToSend);
    
    setLoading(true);
    setCurrentEvaluation(null);

    try {
      const payload = {
        session_id: sessionId,
        video_frames: [],
        audio_base64: '',
        text_answer: answerToSend
      };
      console.log('Payload:', payload);
      
      const response = await axios.post(`${API_BASE}/api/interview/submit-answer`, payload);
      console.log('Response:', response.data);

      if (response.data.success && mountedRef.current) {
        setCurrentEvaluation(response.data.result);
        setTextAnswer('');
        toast.success('Đã ghi nhận câu trả lời!');
      } else {
        console.error('Submit failed:', response.data);
        toast.error(response.data.error || 'Lỗi submit');
      }
    } catch (err) {
      console.error('Submit error:', err);
      toast.error('Lỗi gửi câu trả lời: ' + (err.response?.data?.detail || err.message));
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  // Capture video frame
  const captureFrame = () => {
    if (!videoRef.current || !videoRef.current.videoWidth) return null;
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 320;
      canvas.height = 240;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(videoRef.current, 0, 0, 320, 240);
      return canvas.toDataURL('image/jpeg', 0.6).split(',')[1];
    } catch (e) {
      console.error('Frame capture error:', e);
      return null;
    }
  };

  // Start recording (video frames + audio)
  const startVideoAnswer = async () => {
    if (!cameraOn) {
      const success = await startCamera();
      if (!success) return;
      // Wait for streams to initialize
      await new Promise(r => setTimeout(r, 500));
    }

    // Reset states
    setCapturedFrames([]);
    setAudioBlob(null);
    setTranscriptText('');
    audioChunksRef.current = [];

    // Countdown
    for (let i = 3; i > 0; i--) {
      if (!mountedRef.current) return;
      setCountdown(i);
      await new Promise(r => setTimeout(r, 1000));
    }
    setCountdown(0);

    // Start audio recording
    if (audioStreamRef.current) {
      try {
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
          ? 'audio/webm;codecs=opus' 
          : 'audio/webm';
        
        const recorder = new MediaRecorder(audioStreamRef.current, { mimeType });
        mediaRecorderRef.current = recorder;
        
        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };
        
        recorder.start(1000); // Collect data every second
        console.log('Audio recording started');
      } catch (err) {
        console.error('MediaRecorder error:', err);
      }
    }

    // Start timer and frame capture
    const timeLimit = questions[currentQuestionIdx]?.time_limit || 60;
    setTimeLeft(timeLimit);
    setIsRecording(true);

    // Capture frames every 3 seconds for face analysis
    frameIntervalRef.current = setInterval(() => {
      const frame = captureFrame();
      if (frame) {
        setCapturedFrames(prev => [...prev.slice(-2), frame]); // Keep last 3 frames
      }
    }, 3000);

    // Timer countdown
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) {
          stopVideoAnswer();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  // Stop recording
  const stopVideoAnswer = async () => {
    setIsRecording(false);
    
    // Stop intervals
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    // Capture final frame
    const finalFrame = captureFrame();
    if (finalFrame) {
      setCapturedFrames(prev => [...prev, finalFrame]);
    }

    // Stop audio recording and get blob
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      
      // Wait for final data
      await new Promise(resolve => {
        mediaRecorderRef.current.onstop = resolve;
      });
      
      // Create audio blob
      if (audioChunksRef.current.length > 0) {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setAudioBlob(blob);
        console.log('Audio blob created:', blob.size, 'bytes');
      }
    }

    setVideoRecorded(true);
    toast.success('Đã ghi xong! Đang xử lý âm thanh...');
  };

  // Convert blob to base64
  const blobToBase64 = (blob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  };

  // Submit with audio (auto-transcribe on backend)
  const submitWithAudio = async () => {
    setLoading(true);
    setCurrentEvaluation(null);

    try {
      let audioBase64 = '';
      if (audioBlob) {
        audioBase64 = await blobToBase64(audioBlob);
        console.log('Audio base64 length:', audioBase64.length);
      }

      // Get best frames (first, middle, last)
      const framesToSend = capturedFrames.slice(-3);
      console.log('Sending', framesToSend.length, 'frames');

      const payload = {
        session_id: sessionId,
        video_frames: framesToSend,
        audio_base64: audioBase64,
        text_answer: transcriptText.trim() || '' // Manual transcript if provided
      };

      const response = await axios.post(`${API_BASE}/api/interview/submit-answer`, payload);

      if (response.data.success && mountedRef.current) {
        setCurrentEvaluation(response.data.result);
        resetRecordingState();
        toast.success('Đã ghi nhận câu trả lời!');
      } else {
        toast.error(response.data.error || 'Lỗi submit');
      }
    } catch (err) {
      console.error('Submit error:', err);
      toast.error('Lỗi gửi câu trả lời!');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  // Submit with manual transcript (fallback)
  const submitWithManualTranscript = async () => {
    if (!transcriptText.trim()) {
      toast.error('Vui lòng nhập nội dung câu trả lời!');
      return;
    }

    setLoading(true);
    setCurrentEvaluation(null);

    try {
      const framesToSend = capturedFrames.slice(-3);

      const payload = {
        session_id: sessionId,
        video_frames: framesToSend,
        audio_base64: '',
        text_answer: transcriptText.trim()
      };

      const response = await axios.post(`${API_BASE}/api/interview/submit-answer`, payload);

      if (response.data.success && mountedRef.current) {
        setCurrentEvaluation(response.data.result);
        resetRecordingState();
        toast.success('Đã ghi nhận câu trả lời!');
      } else {
        toast.error(response.data.error || 'Lỗi submit');
      }
    } catch (err) {
      console.error('Submit error:', err);
      toast.error('Lỗi gửi câu trả lời!');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  // Reset recording state
  const resetRecordingState = () => {
    setVideoRecorded(false);
    setCapturedFrames([]);
    setAudioBlob(null);
    setTranscriptText('');
    audioChunksRef.current = [];
  };

  // Next question
  const nextQuestion = () => {
    if (currentQuestionIdx < questions.length - 1) {
      setCurrentQuestionIdx(prev => prev + 1);
      setCurrentEvaluation(null);
      setTextAnswer('');
      resetRecordingState();
    } else {
      finishInterview();
    }
  };

  // Finish interview
  const finishInterview = async () => {
    stopCamera();
    setLoading(true);
    
    try {
      const response = await axios.post(`${API_BASE}/api/interview/finish/${sessionId}`);
      if (response.data.success && mountedRef.current) {
        setResult(response.data.report);
        setStage('result');
        toast.success('Hoàn thành phỏng vấn!');
      }
    } catch (err) {
      console.error(err);
      toast.error('Lỗi kết thúc phỏng vấn');
      // Still move to result stage
      setStage('result');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  // Reset
  const resetInterview = () => {
    stopCamera();
    setStage('setup');
    setSessionId(null);
    setQuestions([]);
    setCurrentQuestionIdx(0);
    setResult(null);
    setCurrentEvaluation(null);
    setTextAnswer('');
  };

  // ===== RENDER SETUP =====
  const renderSetup = () => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-2xl mx-auto"
    >
      <div className="card text-center">
        <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <Video className="w-10 h-10 text-white" />
        </div>
        
        <h2 className="text-2xl font-bold mb-2">Phỏng Vấn Ảo AI</h2>
        <p className="text-slate-400 mb-6">
          AI sẽ đặt câu hỏi và đánh giá câu trả lời của bạn
        </p>

        {cvLoading ? (
          <div className="mb-6 p-4 bg-slate-700/50 rounded-xl">
            <LoadingDots />
            <span className="text-slate-400 ml-2">Đang kiểm tra CV...</span>
          </div>
        ) : !cvText ? (
          <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl text-yellow-300">
            <AlertCircle className="w-5 h-5 inline mr-2" />
            Chưa có CV. Vui lòng phân tích CV ở Tab 1 trước!
          </div>
        ) : (
          <div className="mb-6 p-4 bg-green-500/10 border border-green-500/30 rounded-xl text-green-300">
            <CheckCircle className="w-5 h-5 inline mr-2" />
            Đã có CV ({cvText.length} ký tự) - Sẵn sàng!
          </div>
        )}

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={startInterview}
          disabled={loading || !cvText || cvLoading}
          className="btn-primary text-lg inline-flex items-center gap-3"
        >
          {loading ? <LoadingDots /> : (
            <>
              <Play className="w-6 h-6" />
              Bắt Đầu Phỏng Vấn
            </>
          )}
        </motion.button>

        <div className="mt-8 grid grid-cols-3 gap-4 text-sm">
          <div className="p-3 bg-slate-800/50 rounded-xl">
            <MessageSquare className="w-6 h-6 text-purple-400 mx-auto mb-2" />
            <div className="text-slate-300">3 câu hỏi</div>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-xl">
            <Clock className="w-6 h-6 text-blue-400 mx-auto mb-2" />
            <div className="text-slate-300">~10 phút</div>
          </div>
          <div className="p-3 bg-slate-800/50 rounded-xl">
            <Award className="w-6 h-6 text-yellow-400 mx-auto mb-2" />
            <div className="text-slate-300">Đánh giá AI</div>
          </div>
        </div>
      </div>
    </motion.div>
  );

  // ===== RENDER INTERVIEW =====
  const renderInterview = () => {
    const currentQ = questions[currentQuestionIdx];
    if (!currentQ) return null;

    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="grid lg:grid-cols-2 gap-6"
      >
        {/* Left: Video or Text Input */}
        <div className="card">
          {/* Mode Toggle */}
          <div className="flex justify-center gap-2 mb-4">
            <button
              onClick={() => setUseTextMode(false)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                !useTextMode 
                  ? 'bg-purple-500 text-white' 
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <Video className="w-4 h-4 inline mr-1" />
              Video
            </button>
            <button
              onClick={() => setUseTextMode(true)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                useTextMode 
                  ? 'bg-purple-500 text-white' 
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <MessageSquare className="w-4 h-4 inline mr-1" />
              Text (Ổn định)
            </button>
          </div>

          {useTextMode ? (
            /* TEXT MODE */
            <div className="space-y-4">
              <textarea
                value={textAnswer}
                onChange={(e) => setTextAnswer(e.target.value)}
                placeholder="Nhập câu trả lời của bạn..."
                className="w-full h-48 bg-slate-800 border border-slate-600 rounded-xl p-4 text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 resize-none"
                disabled={loading}
              />
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={submitTextAnswer}
                disabled={loading || !textAnswer.trim()}
                className="w-full btn-primary flex items-center justify-center gap-2"
              >
                {loading ? <LoadingDots /> : (
                  <>
                    <ChevronRight className="w-5 h-5" />
                    Gửi câu trả lời
                  </>
                )}
              </motion.button>
            </div>
          ) : (
            /* VIDEO MODE */
            <div>
              {!videoRecorded ? (
                /* Recording Phase */
                <>
                  <div className="aspect-video bg-slate-900 rounded-xl overflow-hidden mb-4 relative">
                    <video
                      ref={videoRef}
                      autoPlay
                      muted
                      playsInline
                      className="w-full h-full object-cover"
                    />
                    
                    {!cameraOn && (
                      <div className="absolute inset-0 flex items-center justify-center flex-col gap-2">
                        <VideoOff className="w-16 h-16 text-slate-600" />
                        <p className="text-slate-500 text-sm">Camera chưa bật</p>
                      </div>
                    )}

                    {countdown > 0 && (
                      <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
                        <div className="text-8xl font-bold text-purple-400 animate-pulse">
                          {countdown}
                        </div>
                      </div>
                    )}

                    {isRecording && (
                      <>
                        <div className="absolute top-4 left-4 flex items-center gap-2">
                          <div className="flex items-center gap-2 px-3 py-1 bg-red-500/80 rounded-full">
                            <div className="w-3 h-3 bg-white rounded-full animate-pulse" />
                            <span className="text-white text-sm">REC</span>
                          </div>
                          <div className="flex items-center gap-1 px-3 py-1 bg-blue-500/80 rounded-full">
                            <Mic className="w-3 h-3 text-white" />
                            <span className="text-white text-sm">🎙️</span>
                          </div>
                        </div>
                        <div className="absolute top-4 right-4 px-3 py-1 bg-slate-900/80 rounded-full">
                          <Clock className="w-4 h-4 inline mr-1 text-yellow-400" />
                          <span className={`font-mono ${timeLeft < 30 ? 'text-red-400' : 'text-white'}`}>
                            {formatTime(timeLeft)}
                          </span>
                        </div>
                        <div className="absolute bottom-4 left-4 right-4 text-center">
                          <p className="text-white/70 text-sm bg-black/50 rounded-lg py-1 px-3 inline-block">
                            🎤 Đang ghi âm... Hãy nói câu trả lời của bạn
                          </p>
                        </div>
                      </>
                    )}
                  </div>

                  <div className="flex justify-center gap-4">
                    {!cameraOn ? (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={startCamera}
                        className="btn-primary flex items-center gap-2"
                      >
                        <Video className="w-5 h-5" />
                        Bật Camera & Mic
                      </motion.button>
                    ) : !isRecording ? (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={startVideoAnswer}
                        disabled={loading || countdown > 0}
                        className="btn-primary flex items-center gap-2"
                      >
                        <Play className="w-5 h-5" />
                        Bắt đầu trả lời
                      </motion.button>
                    ) : (
                      <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={stopVideoAnswer}
                        className="px-6 py-3 bg-red-500 hover:bg-red-600 rounded-xl font-semibold text-white flex items-center gap-2"
                      >
                        <Square className="w-5 h-5" />
                        Dừng ghi
                      </motion.button>
                    )}
                  </div>
                  
                  <p className="text-center text-slate-400 text-sm mt-3">
                    📹 Video (phân tích khuôn mặt) + 🎤 Âm thanh (chuyển thành text)
                  </p>
                </>
              ) : (
                /* After Recording - Review & Submit */
                <div className="space-y-4">
                  {/* Status */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className={`p-3 rounded-xl text-center ${
                      capturedFrames.length > 0 
                        ? 'bg-green-500/10 border border-green-500/30 text-green-300'
                        : 'bg-red-500/10 border border-red-500/30 text-red-300'
                    }`}>
                      <Video className="w-6 h-6 mx-auto mb-1" />
                      <p className="text-sm">{capturedFrames.length} frames</p>
                    </div>
                    <div className={`p-3 rounded-xl text-center ${
                      audioBlob 
                        ? 'bg-green-500/10 border border-green-500/30 text-green-300'
                        : 'bg-yellow-500/10 border border-yellow-500/30 text-yellow-300'
                    }`}>
                      <Mic className="w-6 h-6 mx-auto mb-1" />
                      <p className="text-sm">
                        {audioBlob ? `${Math.round(audioBlob.size / 1024)} KB` : 'Không có'}
                      </p>
                    </div>
                  </div>

                  {/* Audio available - auto transcribe option */}
                  {audioBlob ? (
                    <div className="space-y-3">
                      <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl text-blue-300 text-sm">
                        <Mic className="w-4 h-4 inline mr-2" />
                        Đã ghi âm thành công! AI sẽ chuyển âm thanh thành text.
                      </div>
                      
                      <div className="text-slate-400 text-sm text-center">hoặc nhập thủ công:</div>
                      
                      <textarea
                        value={transcriptText}
                        onChange={(e) => setTranscriptText(e.target.value)}
                        placeholder="(Tùy chọn) Nhập lại nội dung nếu muốn..."
                        className="w-full h-24 bg-slate-800 border border-slate-600 rounded-xl p-3 text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 resize-none text-sm"
                        disabled={loading}
                      />
                      
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={submitWithAudio}
                        disabled={loading}
                        className="w-full btn-primary flex items-center justify-center gap-2"
                      >
                        {loading ? <LoadingDots /> : (
                          <>
                            <ChevronRight className="w-5 h-5" />
                            Gửi (AI tự động chuyển text)
                          </>
                        )}
                      </motion.button>
                    </div>
                  ) : (
                    /* No audio - manual transcript required */
                    <div className="space-y-3">
                      <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl text-yellow-300 text-sm">
                        <AlertCircle className="w-4 h-4 inline mr-2" />
                        Không ghi được âm thanh. Vui lòng nhập nội dung thủ công.
                      </div>
                      
                      <textarea
                        value={transcriptText}
                        onChange={(e) => setTranscriptText(e.target.value)}
                        placeholder="Nhập nội dung câu trả lời của bạn..."
                        className="w-full h-32 bg-slate-800 border border-slate-600 rounded-xl p-4 text-white placeholder-slate-400 focus:outline-none focus:border-purple-500 resize-none"
                        disabled={loading}
                        autoFocus
                      />
                      
                      <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={submitWithManualTranscript}
                        disabled={loading || !transcriptText.trim()}
                        className="w-full btn-primary flex items-center justify-center gap-2"
                      >
                        {loading ? <LoadingDots /> : (
                          <>
                            <ChevronRight className="w-5 h-5" />
                            Gửi câu trả lời
                          </>
                        )}
                      </motion.button>
                    </div>
                  )}
                  
                  {/* Re-record button */}
                  <button
                    onClick={resetRecordingState}
                    className="w-full px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-xl text-slate-300 text-sm"
                  >
                    ↻ Ghi lại
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Question & Evaluation */}
        <div className="space-y-4">
          {/* Progress */}
          <div className="card">
            <div className="flex justify-between items-center mb-2">
              <span className="text-slate-400">Tiến độ</span>
              <span className="text-purple-300 font-medium">
                {currentQuestionIdx + 1} / {questions.length}
              </span>
            </div>
            <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                initial={{ width: 0 }}
                animate={{ width: `${((currentQuestionIdx + 1) / questions.length) * 100}%` }}
              />
            </div>
          </div>

          {/* Question */}
          <div className="card">
            <div className="flex items-start gap-3 mb-4">
              <div className="w-10 h-10 bg-purple-500/20 rounded-xl flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <div className="text-sm text-purple-400 mb-1">
                  Câu hỏi {currentQuestionIdx + 1}
                  {currentQ.type && (
                    <span className="ml-2 px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300">
                      {currentQ.type}
                    </span>
                  )}
                </div>
                <p className="text-lg text-white">{currentQ.question}</p>
              </div>
            </div>
          </div>

          {/* Evaluation */}
          <AnimatePresence>
            {currentEvaluation && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="card border border-purple-500/30"
              >
                <h3 className="font-semibold text-purple-300 mb-4 flex items-center gap-2">
                  <Award className="w-5 h-5" />
                  Đánh giá
                </h3>

                {currentEvaluation.answer_evaluation && (
                  <>
                    <div className="flex gap-3 mb-4 flex-wrap">
                      <ScoreBadge 
                        score={currentEvaluation.answer_evaluation.relevance_score || 5} 
                        label="Liên quan" 
                      />
                      <ScoreBadge 
                        score={currentEvaluation.answer_evaluation.completeness_score || 5} 
                        label="Đầy đủ" 
                      />
                      <ScoreBadge 
                        score={currentEvaluation.answer_evaluation.overall_score || 5} 
                        label="Tổng" 
                      />
                    </div>

                    {/* Show transcript */}
                    {currentEvaluation.transcript && (
                      <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-xl text-sm text-blue-200 mb-3">
                        <div className="text-xs text-blue-400 mb-1">📝 Câu trả lời đã ghi nhận:</div>
                        <div className="italic">"{currentEvaluation.transcript}"</div>
                      </div>
                    )}

                    <div className="p-3 bg-slate-800/50 rounded-xl text-sm text-slate-300">
                      <div className="text-xs text-slate-400 mb-1">💡 Nhận xét:</div>
                      {currentEvaluation.answer_evaluation.feedback || 'Không có nhận xét'}
                    </div>

                    {/* Show ideal answer if available */}
                    {currentEvaluation.answer_evaluation.ideal_answer && (
                      <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-xl text-sm text-green-200 mt-3">
                        <div className="text-xs text-green-400 mb-1">✨ Câu trả lời mẫu:</div>
                        {currentEvaluation.answer_evaluation.ideal_answer}
                      </div>
                    )}
                  </>
                )}

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={nextQuestion}
                  className="w-full btn-primary mt-4 flex items-center justify-center gap-2"
                >
                  {currentQuestionIdx < questions.length - 1 ? (
                    <>
                      Câu tiếp theo
                      <ChevronRight className="w-5 h-5" />
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-5 h-5" />
                      Hoàn thành
                    </>
                  )}
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>

          {loading && !currentEvaluation && (
            <div className="card text-center py-8">
              <LoadingDots />
              <p className="text-slate-400 mt-2">Đang đánh giá...</p>
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  // ===== RENDER RESULT =====
  const renderResult = () => (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="max-w-3xl mx-auto"
    >
      <div className="card text-center mb-6">
        <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle className="w-10 h-10 text-white" />
        </div>
        <h2 className="text-2xl font-bold mb-2">Hoàn Thành Phỏng Vấn!</h2>
        <p className="text-slate-400">Dưới đây là kết quả đánh giá của AI</p>
      </div>

      {result ? (
        <div className="card">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <ScoreBadge score={result.communication_score || 5} label="Giao tiếp" />
            <ScoreBadge score={result.confidence_score || 5} label="Tự tin" />
            <ScoreBadge score={result.professionalism_score || 5} label="Chuyên nghiệp" />
            <ScoreBadge score={result.overall_behavioral_score || 5} label="Tổng thể" />
          </div>

          <div className={`p-4 rounded-xl text-center mb-6 ${
            result.hiring_recommendation === 'Recommend' 
              ? 'bg-green-500/10 border border-green-500/30 text-green-300'
              : result.hiring_recommendation === 'Consider'
              ? 'bg-yellow-500/10 border border-yellow-500/30 text-yellow-300'
              : 'bg-red-500/10 border border-red-500/30 text-red-300'
          }`}>
            <Award className="w-8 h-8 mx-auto mb-2" />
            <div className="text-xl font-bold">{result.hiring_recommendation || 'N/A'}</div>
          </div>

          {result.strengths?.length > 0 && (
            <div className="mb-4">
              <h4 className="font-semibold text-green-400 mb-2">✅ Điểm mạnh</h4>
              <ul className="space-y-1 text-sm text-slate-300">
                {result.strengths.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {result.areas_to_improve?.length > 0 && (
            <div className="mb-4">
              <h4 className="font-semibold text-yellow-400 mb-2">⚠️ Cần cải thiện</h4>
              <ul className="space-y-1 text-sm text-slate-300">
                {result.areas_to_improve.map((s, i) => (
                  <li key={i}>• {s}</li>
                ))}
              </ul>
            </div>
          )}

          {result.detailed_feedback && (
            <div className="p-4 bg-slate-800/50 rounded-xl text-slate-300">
              <h4 className="font-semibold mb-2">📝 Nhận xét chi tiết</h4>
              <p>{result.detailed_feedback}</p>
            </div>
          )}
        </div>
      ) : (
        <div className="card text-center py-8 text-slate-400">
          Không có dữ liệu đánh giá
        </div>
      )}

      <div className="text-center mt-6">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={resetInterview}
          className="btn-primary inline-flex items-center gap-2"
        >
          <RefreshCw className="w-5 h-5" />
          Phỏng vấn lại
        </motion.button>
      </div>
    </motion.div>
  );

  // Main render
  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold gradient-text mb-2">
          🎥 Phỏng Vấn Ảo AI
        </h1>
        <p className="text-slate-400">
          Luyện tập phỏng vấn với trí tuệ nhân tạo
        </p>
      </div>

      {stage === 'setup' && renderSetup()}
      {stage === 'interview' && renderInterview()}
      {stage === 'result' && renderResult()}
    </div>
  );
}

// Export with Error Boundary
export default function InterviewTab() {
  return (
    <ErrorBoundary>
      <InterviewContent />
    </ErrorBoundary>
  );
}
