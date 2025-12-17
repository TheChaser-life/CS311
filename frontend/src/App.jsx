// Ứng dụng React chính điều phối toàn bộ trải nghiệm Smart Resume Analyzer.
// File này giữ state ở cấp cao nhất, định nghĩa từng tab tính năng và xử lý
// việc giao tiếp với backend thông qua axios.
import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, Search, Sparkles, MessageCircle,
  Upload, Send, Loader2, CheckCircle2, AlertCircle,
  Briefcase, GraduationCap, Target, ArrowRight, Trash2
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useDropzone } from 'react-dropzone';
import toast, { Toaster } from 'react-hot-toast';
import axios from 'axios';

// Backend có thể được reverse proxy bằng Nginx nên mặc định sử dụng relative path.
// Trường hợp build-time muốn override có thể truyền VITE_API_BASE, nếu không sẽ trả chuỗi rỗng.
const resolveApiBase = () => import.meta.env?.VITE_API_BASE ?? '';

const SESSION_STORAGE_KEY = 'resume_session_id';

// Sinh sessionId lưu vào localStorage để backend bám theo Redis session tương ứng.
const generateSessionId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return [
    'sess',
    Date.now().toString(36),
    Math.random().toString(36).substring(2, 10),
  ].join('-');
};

// Cấu hình các tab chính hiển thị trên navbar.
const tabs = [
  { id: 'analyze', label: 'Phân Tích CV-JD', icon: FileText },
  { id: 'jobs', label: 'Tìm Việc Làm', icon: Search },
  { id: 'improve', label: 'Cải Thiện CV', icon: Sparkles },
  { id: 'chat', label: 'Chat AI', icon: MessageCircle },
];

// ========== UI HELPERS ==========
// Spinner đơn giản dùng chung cho nhiều state loading.
const LoadingDots = () => (
  <div className="loading-dots">
    <span></span>
    <span></span>
    <span></span>
  </div>
);

// Ô upload hỗ trợ kéo thả và hiển thị trạng thái file được chọn.
const FileDropzone = ({ onDrop, label, accept }) => {
  const { getRootProps, getInputProps, isDragActive, acceptedFiles } = useDropzone({
    onDrop,
    accept,
    maxFiles: 1
  });

  return (
    <div
      {...getRootProps()}
      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-300
        ${isDragActive 
          ? 'border-purple-500 bg-purple-500/10' 
          : 'border-slate-600 hover:border-purple-500/50 hover:bg-slate-800/30'}`}
    >
      <input {...getInputProps()} />
      <Upload className={`w-12 h-12 mx-auto mb-4 ${isDragActive ? 'text-purple-400' : 'text-slate-500'}`} />
      {acceptedFiles.length > 0 ? (
        <div className="text-green-400 flex items-center justify-center gap-2">
          <CheckCircle2 className="w-5 h-5" />
          {acceptedFiles[0].name}
        </div>
      ) : (
        <>
          <p className="text-slate-300 font-medium">{label}</p>
          <p className="text-slate-500 text-sm mt-2">Kéo thả hoặc click để chọn file</p>
          <p className="text-slate-600 text-xs mt-1">PDF, PNG, JPG (Max 10MB)</p>
        </>
      )}
    </div>
  );
};

// Tùy biến Markdown để các liên kết mở tab mới và giữ style thống nhất.
const markdownComponents = {
  a: ({ node, ...props }) => (
    <a
      {...props}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-400 underline hover:text-blue-300 transition-colors"
    />
  ),
};

// Bao bọc hiển thị kết quả dưới dạng thẻ, hỗ trợ trạng thái loading.
const ResultCard = ({ result, loading }) => {
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="card"
      >
        <div className="flex items-center gap-3">
          <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
          <span className="text-slate-300">AI đang xử lý...</span>
          <LoadingDots />
        </div>
      </motion.div>
    );
  }

  if (!result) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="card markdown-content"
    >
      <ReactMarkdown components={markdownComponents}>{result}</ReactMarkdown>
    </motion.div>
  );
};

// ========== TAB: PHÂN TÍCH CV so với JD ==========
const AnalyzeTab = ({ state, setState, sessionReady }) => {
  const [cvFile, setCvFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);
  const [cvText, setCvText] = useState('');
  const [jdText, setJdText] = useState('');
  const [cvMode, setCvMode] = useState('text');
  const [jdMode, setJdMode] = useState('text');
  const { loading, result } = state;

  // Gửi nội dung CV/JD (từ file hoặc text) lên backend để phân tích bằng agent.
  const handleAnalyze = async () => {
    if (!sessionReady) {
      toast.error('Đang khởi tạo phiên làm việc, vui lòng thử lại sau!');
      return;
    }

    setState(prev => ({ ...prev, loading: true, result: '' }));
    
    try {
      const formData = new FormData();
      
      if (cvMode === 'file' && cvFile) {
        formData.append('cv_file', cvFile);
      } else {
        formData.append('cv_text', cvText);
      }
      
      if (jdMode === 'file' && jdFile) {
        formData.append('jd_file', jdFile);
      } else {
        formData.append('jd_text', jdText);
      }

      const response = await axios.post('/api/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setState(prev => ({ ...prev, result: response.data.result }));
        // Show storage status
        if (response.data.cv_stored) {
          toast.success('CV đã được lưu!', { duration: 2000 });
        }
        toast.success('Phân tích hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
      console.error(error);
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="space-y-6 animate-in">
      <div className="grid md:grid-cols-2 gap-6">
        {/* CV Section */}
        <div className="card">
          <h3 className="text-xl font-semibold text-purple-300 mb-4 flex items-center gap-2">
            <FileText className="w-5 h-5" />
            CV của bạn
          </h3>
          
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setCvMode('text')}
              className={`px-4 py-2 rounded-lg transition-all ${
                cvMode === 'text' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              Nhập Text
            </button>
            <button
              onClick={() => setCvMode('file')}
              className={`px-4 py-2 rounded-lg transition-all ${
                cvMode === 'file' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              Upload File
            </button>
          </div>

          {cvMode === 'text' ? (
            <textarea
              value={cvText}
              onChange={(e) => setCvText(e.target.value)}
              placeholder="Paste nội dung CV vào đây..."
              className="textarea-glass h-64"
            />
          ) : (
            <FileDropzone
              onDrop={(files) => setCvFile(files[0])}
              label="Upload CV"
              accept={{ 'application/pdf': ['.pdf'], 'image/*': ['.png', '.jpg', '.jpeg'] }}
            />
          )}
        </div>

        {/* JD Section */}
        <div className="card">
          <h3 className="text-xl font-semibold text-indigo-300 mb-4 flex items-center gap-2">
            <Briefcase className="w-5 h-5" />
            Job Description
          </h3>
          
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setJdMode('text')}
              className={`px-4 py-2 rounded-lg transition-all ${
                jdMode === 'text' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              Nhập Text
            </button>
            <button
              onClick={() => setJdMode('file')}
              className={`px-4 py-2 rounded-lg transition-all ${
                jdMode === 'file' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30' : 'text-slate-400 hover:text-white'
              }`}
            >
              Upload File
            </button>
          </div>

          {jdMode === 'text' ? (
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste nội dung JD vào đây..."
              className="textarea-glass h-64"
            />
          ) : (
            <FileDropzone
              onDrop={(files) => setJdFile(files[0])}
              label="Upload JD"
              accept={{ 'application/pdf': ['.pdf'], 'image/*': ['.png', '.jpg', '.jpeg'] }}
            />
          )}
        </div>
      </div>

      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={handleAnalyze}
        disabled={loading || !sessionReady}
        className="btn-primary w-full text-lg flex items-center justify-center gap-3"
      >
        {loading ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Đang phân tích...
          </>
        ) : (
          <>
            <Target className="w-5 h-5" />
            Phân Tích CV-JD
            <ArrowRight className="w-5 h-5" />
          </>
        )}
      </motion.button>

      <ResultCard result={result} loading={loading} />
    </div>
  );
};

// ========== TAB: GỢI Ý VIỆC LÀM ==========
const JobsTab = ({ state, setState, sessionReady }) => {
  const { loading, result } = state;

  // Yêu cầu backend tìm danh sách việc làm dựa trên CV lưu trong session.
  const handleFindJobs = async () => {
    if (!sessionReady) {
      toast.error('Đang khởi tạo phiên làm việc, vui lòng thử lại sau!');
      return;
    }

    setState(prev => ({ ...prev, loading: true, result: '' }));
    
    try {
      const response = await axios.post('/api/find-jobs');
      
      if (response.data.success) {
        setState(prev => ({ ...prev, result: response.data.result }));
        toast.success('Tìm việc hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  return (
    <div className="space-y-6 animate-in">
      <div className="card">
        <div className="text-center">
          <Search className="w-16 h-16 mx-auto text-purple-400 mb-4" />
          <h3 className="text-2xl font-bold gradient-text mb-3">Tìm Việc Làm Phù Hợp</h3>
          <p className="text-slate-400 mb-6 max-w-lg mx-auto">
            AI sẽ phân tích CV của bạn và tìm kiếm các công việc phù hợp nhất trên mạng, 
            bao gồm đánh giá khả năng phỏng vấn.
          </p>
          
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleFindJobs}
            disabled={loading || !sessionReady}
            className="btn-primary text-lg inline-flex items-center gap-3"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Đang tìm kiếm...
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                Tìm Việc Ngay
              </>
            )}
          </motion.button>
        </div>
      </div>

      <ResultCard result={result} loading={loading} />

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card text-center">
          <Target className="w-8 h-8 mx-auto text-green-400 mb-2" />
          <h4 className="font-semibold text-slate-200">Phân tích CV</h4>
          <p className="text-slate-500 text-sm">Xác định điểm mạnh</p>
        </div>
        <div className="card text-center">
          <Briefcase className="w-8 h-8 mx-auto text-blue-400 mb-2" />
          <h4 className="font-semibold text-slate-200">Tìm việc online</h4>
          <p className="text-slate-500 text-sm">LinkedIn, TopCV...</p>
        </div>
        <div className="card text-center">
          <GraduationCap className="w-8 h-8 mx-auto text-purple-400 mb-2" />
          <h4 className="font-semibold text-slate-200">Đánh giá PV</h4>
          <p className="text-slate-500 text-sm">Khả năng được gọi</p>
        </div>
      </div>
    </div>
  );
};

// ========== TAB: CẢI THIỆN CV ==========
const ImproveTab = ({ state, setState, sessionReady }) => {
  const { loading, layoutLoading, result, layoutResult, docxWarning } = state;
  const [layoutFile, setLayoutFile] = useState(null);

  // Gọi agent viết lại CV bằng tiếng Anh và trả về đề xuất cải thiện.
  const handleSuggestImprovements = async () => {
    if (!sessionReady) {
      toast.error('Đang khởi tạo phiên làm việc, vui lòng thử lại sau!');
      return;
    }

    setState(prev => ({
      ...prev,
      loading: true,
      result: '',
      docxWarning: ''
    }));
    
    try {
      const response = await axios.post('/api/suggest-cv-improvements');
      
      if (response.data.success) {
        setState(prev => ({ ...prev, result: response.data.result }));
        if (response.data.warning) {
          setState(prev => ({ ...prev, docxWarning: response.data.warning }));
          toast.error(response.data.warning);
        } else {
          toast.success('Đề xuất hoàn tất!');
        }
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  // Upload ảnh/PDF CV để AI đánh giá bố cục hình ảnh.
  const handleAnalyzeLayout = async () => {
    if (!sessionReady) {
      toast.error('Đang khởi tạo phiên làm việc, vui lòng thử lại sau!');
      return;
    }

    if (!layoutFile) {
      toast.error('Vui lòng upload ảnh CV!');
      return;
    }

    setState(prev => ({ ...prev, layoutLoading: true, layoutResult: '' }));
    
    try {
      const formData = new FormData();
      formData.append('file', layoutFile);

      const response = await axios.post('/api/analyze-cv-layout', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setState(prev => ({ ...prev, layoutResult: response.data.result }));
        toast.success('Phân tích layout hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setState(prev => ({ ...prev, layoutLoading: false }));
    }
  };

  return (
    <div className="space-y-6 animate-in">
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card">
          <Sparkles className="w-10 h-10 text-purple-400 mb-4" />
          <h3 className="text-xl font-semibold text-purple-300 mb-3">Đề Xuất Chỉnh Sửa CV</h3>
          <p className="text-slate-400 mb-4">
            AI sẽ phân tích và viết lại CV của bạn với format tối ưu hơn.
          </p>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleSuggestImprovements}
            disabled={loading || !sessionReady}
            className="btn-primary w-full"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Đề Xuất Chỉnh Sửa'}
          </motion.button>
        </div>

        <div className="card">
          <FileText className="w-10 h-10 text-indigo-400 mb-4" />
          <h3 className="text-xl font-semibold text-indigo-300 mb-3">Kiểm Tra Layout CV</h3>
          <p className="text-slate-400 mb-4">
            Upload ảnh CV để AI đánh giá bố cục và thiết kế.
          </p>
          <FileDropzone
            onDrop={(files) => setLayoutFile(files[0])}
            label="Upload ảnh CV"
            accept={{ 'application/pdf': ['.pdf'], 'image/*': ['.png', '.jpg', '.jpeg'] }}
          />
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleAnalyzeLayout}
            disabled={layoutLoading || !layoutFile || !sessionReady}
            className="btn-secondary w-full mt-4"
          >
            {layoutLoading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Phân Tích Layout'}
          </motion.button>
        </div>
      </div>

      <ResultCard result={result} loading={loading} />

      {docxWarning && (
        <div className="card border border-yellow-500/40 bg-yellow-500/10 text-sm text-yellow-200">
          {docxWarning}
        </div>
      )}

      <ResultCard result={layoutResult} loading={layoutLoading} />
    </div>
  );
};

// ========== TAB: CHAT AI ==========
const ChatTab = ({ state, setState, sessionReady }) => {
  const { messages, loading } = state;
  const [input, setInput] = useState('');

  // Gửi câu hỏi tới backend và append kết quả vào lịch sử hội thoại.
  const sendMessage = async (text) => {
    if (!text.trim()) return;
    if (!sessionReady) {
      toast.error('Đang khởi tạo phiên làm việc, vui lòng thử lại sau!');
      return;
    }
    
    const userMessage = { role: 'user', content: text };
    setState(prev => ({ ...prev, messages: [...prev.messages, userMessage] }));
    setInput('');
    setState(prev => ({ ...prev, loading: true }));

    try {
      const response = await axios.post('/api/chat', { message: text });
      
      if (response.data.success) {
        const aiMessage = { role: 'assistant', content: response.data.result };
        setState(prev => ({ ...prev, messages: [...prev.messages, aiMessage] }));
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  };

  // Các prompt nhanh giúp người dùng bắt đầu trò chuyện.
  const quickActions = [
    { label: 'Phân tích CV', prompt: 'Hãy phân tích CV của tôi một cách chi tiết' },
    { label: 'Cải thiện CV', prompt: 'Hãy đề xuất chỉnh sửa và viết lại CV của tôi' },
    { label: 'Gợi ý học tập', prompt: 'Đề xuất lộ trình học tập và khóa học phù hợp' },
    { label: 'Tư vấn nghề nghiệp', prompt: 'Cho tôi lời khuyên về sự nghiệp và phát triển' },
  ];

  return (
    <div className="space-y-4 animate-in">
      <div className="card h-[500px] flex flex-col">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 mb-4">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <MessageCircle className="w-16 h-16 mx-auto text-slate-600 mb-4" />
              <p className="text-slate-500">Bắt đầu trò chuyện với AI Assistant!</p>
            </div>
          )}
          
          <AnimatePresence>
            {messages.map((msg, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[80%] p-4 rounded-2xl ${
                  msg.role === 'user' 
                    ? 'bg-gradient-to-r from-indigo-500 to-purple-500 text-white' 
                    : 'bg-slate-800 text-slate-200'
                }`}>
                  {msg.role === 'assistant' ? (
                    <div className="markdown-content">
                      <ReactMarkdown components={markdownComponents}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    msg.content
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          
          {loading && (
            <div className="flex justify-start">
              <div className="bg-slate-800 p-4 rounded-2xl">
                <LoadingDots />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            placeholder="Nhập câu hỏi của bạn..."
            className="input-glass flex-1"
          />
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim() || !sessionReady}
            className="btn-primary px-6"
          >
            <Send className="w-5 h-5" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setState(prev => ({ ...prev, messages: [] }))}
            className="btn-secondary px-4"
          >
            <Trash2 className="w-5 h-5" />
          </motion.button>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        {quickActions.map((action, index) => (
          <motion.button
            key={index}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => sendMessage(action.prompt)}
            className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-xl text-sm text-slate-300 
                     hover:border-purple-500/50 hover:text-purple-300 transition-all"
          >
            {action.label}
          </motion.button>
        ))}
      </div>
    </div>
  );
};

// ========== ỨNG DỤNG CHÍNH ==========
// Quản lý state cho từng tab và thiết lập session/axios mặc định.
export default function App() {
  const [activeTab, setActiveTab] = useState('analyze');
  const [analyzeState, setAnalyzeState] = useState({ loading: false, result: '' });
  const [jobsState, setJobsState] = useState({ loading: false, result: '' });
  const [improveState, setImproveState] = useState({
    loading: false,
    result: '',
    docxWarning: '',
    layoutLoading: false,
    layoutResult: '',
  });
  const [chatState, setChatState] = useState({ messages: [], loading: false });
  const [sessionReady, setSessionReady] = useState(false);

  // Khởi tạo session id (lưu localStorage) và cấu hình axios base headers.
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      let sessionId = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (!sessionId) {
        sessionId = generateSessionId();
        window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
      }

      const apiBase = resolveApiBase();
      axios.defaults.baseURL = apiBase;
      axios.defaults.withCredentials = false;
      axios.defaults.headers.common['X-Session-Id'] = sessionId;
      setSessionReady(true);
    } catch (error) {
      console.error('Failed to initialize session ID', error);
      toast.error('Không thể khởi tạo phiên làm việc. Hãy tải lại trang!');
    }
  }, []);

  // Render tab tương ứng với lựa chọn hiện tại.
  const renderTab = () => {
    switch (activeTab) {
      case 'analyze':
        return (
          <AnalyzeTab
            state={analyzeState}
            setState={setAnalyzeState}
            sessionReady={sessionReady}
          />
        );
      case 'jobs':
        return (
          <JobsTab
            state={jobsState}
            setState={setJobsState}
            sessionReady={sessionReady}
          />
        );
      case 'improve':
        return (
          <ImproveTab
            state={improveState}
            setState={setImproveState}
            sessionReady={sessionReady}
          />
        );
      case 'chat':
        return (
          <ChatTab
            state={chatState}
            setState={setChatState}
            sessionReady={sessionReady}
          />
        );
      default:
        return (
          <AnalyzeTab
            state={analyzeState}
            setState={setAnalyzeState}
            sessionReady={sessionReady}
          />
        );
    }
  };

  return (
    <div className="min-h-screen bg-pattern">
      <Toaster position="top-right" />
      
      {/* Background Effects */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl floating" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl floating-delayed" />
        <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-pink-500/5 rounded-full blur-3xl" />
      </div>

      {/* Header */}
      <header className="relative z-10 py-8 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-3 mb-4"
          >
            <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center">
              <FileText className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-3xl md:text-4xl font-bold gradient-text">
              AI Resume Analyzer
            </h1>
          </motion.div>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="text-slate-400 text-lg"
          >
            Phân tích CV • Tìm việc làm • Cải thiện CV • Chat AI
          </motion.p>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="text-slate-500 text-sm mt-2"
          >
            by Võ Phước Thịnh, Liên Phúc Thịnh 
          </motion.p>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 px-6 pb-12">
        <div className="max-w-6xl mx-auto">
          {!sessionReady && (
            <div className="card border border-slate-700/60 bg-slate-900/60 text-sm text-slate-300 mb-6">
              Đang khởi tạo phiên làm việc với máy chủ...
            </div>
          )}
          {/* Tabs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-wrap justify-center gap-2 mb-8"
          >
            {tabs.map((tab) => (
              <motion.button
                key={tab.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setActiveTab(tab.id)}
                className={`tab flex items-center gap-2 ${
                  activeTab === tab.id ? 'tab-active' : 'tab-inactive'
                }`}
              >
                <tab.icon className="w-5 h-5" />
                {tab.label}
              </motion.button>
            ))}
          </motion.div>

          {/* Tab Content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              {renderTab()}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 py-6 text-center text-slate-500 text-sm">
        <p>Version 0.2 • Powered by Friendship</p>
      </footer>
    </div>
  );
}

