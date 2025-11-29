import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileText, Search, Sparkles, MessageCircle, Video,
  Upload, Send, Loader2, CheckCircle2, AlertCircle,
  Briefcase, GraduationCap, Target, ArrowRight, Trash2
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { useDropzone } from 'react-dropzone';
import toast, { Toaster } from 'react-hot-toast';
import axios from 'axios';
import InterviewTab from './InterviewTab';

const API_BASE = 'http://localhost:8000';

// Tab Configuration
const tabs = [
  { id: 'analyze', label: 'Phân Tích CV-JD', icon: FileText },
  { id: 'jobs', label: 'Tìm Việc Làm', icon: Search },
  { id: 'improve', label: 'Cải Thiện CV', icon: Sparkles },
  { id: 'interview', label: 'Phỏng Vấn Ảo', icon: Video },
  { id: 'chat', label: 'Chat AI', icon: MessageCircle },
];

// Components
const LoadingDots = () => (
  <div className="loading-dots">
    <span></span>
    <span></span>
    <span></span>
  </div>
);

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
      <ReactMarkdown>{result}</ReactMarkdown>
    </motion.div>
  );
};

// Main Tabs
const AnalyzeTab = () => {
  const [cvFile, setCvFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);
  const [cvText, setCvText] = useState('');
  const [jdText, setJdText] = useState('');
  const [cvMode, setCvMode] = useState('text');
  const [jdMode, setJdMode] = useState('text');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState('');

  const handleAnalyze = async () => {
    setLoading(true);
    setResult('');
    
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

      const response = await axios.post(`${API_BASE}/api/analyze`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setResult(response.data.result);
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
      setLoading(false);
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
        disabled={loading}
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

const JobsTab = () => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState('');

  const handleFindJobs = async () => {
    setLoading(true);
    setResult('');
    
    try {
      const response = await axios.post(`${API_BASE}/api/find-jobs`);
      
      if (response.data.success) {
        setResult(response.data.result);
        toast.success('Tìm việc hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setLoading(false);
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
            disabled={loading}
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

const ImproveTab = () => {
  const [loading, setLoading] = useState(false);
  const [layoutLoading, setLayoutLoading] = useState(false);
  const [result, setResult] = useState('');
  const [layoutResult, setLayoutResult] = useState('');
  const [layoutFile, setLayoutFile] = useState(null);

  const handleSuggestImprovements = async () => {
    setLoading(true);
    setResult('');
    
    try {
      const response = await axios.post(`${API_BASE}/api/suggest-cv-improvements`);
      
      if (response.data.success) {
        setResult(response.data.result);
        toast.success('Đề xuất hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeLayout = async () => {
    if (!layoutFile) {
      toast.error('Vui lòng upload ảnh CV!');
      return;
    }

    setLayoutLoading(true);
    setLayoutResult('');
    
    try {
      const formData = new FormData();
      formData.append('file', layoutFile);

      const response = await axios.post(`${API_BASE}/api/analyze-cv-layout`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (response.data.success) {
        setLayoutResult(response.data.result);
        toast.success('Phân tích layout hoàn tất!');
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setLayoutLoading(false);
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
            disabled={loading}
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
            disabled={layoutLoading || !layoutFile}
            className="btn-secondary w-full mt-4"
          >
            {layoutLoading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Phân Tích Layout'}
          </motion.button>
        </div>
      </div>

      <ResultCard result={result} loading={loading} />
      <ResultCard result={layoutResult} loading={layoutLoading} />
    </div>
  );
};

const ChatTab = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    
    const userMessage = { role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/chat`, { message: text });
      
      if (response.data.success) {
        const aiMessage = { role: 'assistant', content: response.data.result };
        setMessages(prev => [...prev, aiMessage]);
      } else {
        toast.error(response.data.result);
      }
    } catch (error) {
      toast.error('Lỗi kết nối server!');
    } finally {
      setLoading(false);
    }
  };

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
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
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
            disabled={loading || !input.trim()}
            className="btn-primary px-6"
          >
            <Send className="w-5 h-5" />
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setMessages([])}
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

// Main App
export default function App() {
  const [activeTab, setActiveTab] = useState('analyze');

  const renderTab = () => {
    switch (activeTab) {
      case 'analyze': return <AnalyzeTab />;
      case 'jobs': return <JobsTab />;
      case 'improve': return <ImproveTab />;
      case 'interview': return <InterviewTab />;
      case 'chat': return <ChatTab />;
      default: return <AnalyzeTab />;
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
            by Võ Phước Thịnh, Liên Phúc Thịnh & Nguyễn Tấn Phúc Thịnh
          </motion.p>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 px-6 pb-12">
        <div className="max-w-6xl mx-auto">
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
        <p>Version 3.0 • Powered by GPT-4o & LangChain</p>
      </footer>
    </div>
  );
}

