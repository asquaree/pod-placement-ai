# NetTune AI Architecture Documentation

## 🏗️ System Architecture

NetTune AI follows a clean separation of concerns with distinct **Backend** and **Frontend** layers, providing maintainable, scalable, and modular code structure.

## 📁 File Structure

```
NetTune AI/
├── nettune_backend.py      # Backend service (Business Logic)
├── nettune_frontend.py     # Frontend UI (Streamlit Interface)
├── pod_placement_assistant.py  # Original monolithic version
├── requirements.txt        # Python dependencies
├── launch_nettune.bat     # Windows launcher
├── README.md              # General documentation
├── README_UI.md           # UI-specific documentation
└── ARCHITECTURE.md        # This file
```

## 🔄 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                    │
│  ┌─────────────────────────────────────────────────────────┤
│  │              Streamlit Frontend                         │
│  │  - Chat Interface                                       │
│  │  - User Input Handling                                  │
│  │  - Session State Management                             │
│  │  - UI Components & Styling                              │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                                │
                       ┌────────▼────────┐
                       │  API Interface  │
                       │  (Clean Methods)│
                       └────────┬────────┘
                                │
┌─────────────────────────────────────────────────────────────┐
│                   BACKEND SERVICE LAYER                    │
│  ┌─────────────────────────────────────────────────────────┤
│  │              NetTune Backend                            │
│  │                                                         │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  │DataProcessor│  │QueryProcessor│  │ResponseProcessor│ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │
│  │                                                         │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │  │VectorStore  │  │   GapLLM    │  │  TokenCounter   │ │
│  │  │  Manager    │  │ Integration │  │                 │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ │
│  └─────────────────────────────────────────────────────────┤
└─────────────────────────────────────────────────────────────┘
                                │
                       ┌────────▼────────┐
                       │   Data Layer    │
                       │  - CSV Files    │
                       │  - Vector Stores│
                       │  - DR Rules     │
                       └─────────────────┘
```

---

## 🏛️ Backend Architecture (`nettune_backend.py`)

### **Core Classes**

#### **1. NetTuneBackend** (Main Service)
```python
class NetTuneBackend:
    - initialize(tokenizer_path) -> Dict
    - process_query(question, history, df_result) -> Dict  
    - get_status() -> Dict
    - reset_session() -> Dict
    - num_tokens(text) -> int
    - route_query(query) -> str
```

#### **2. DataProcessor**
```python
class DataProcessor:
    - load_csv_data() -> Tuple[Documents, ...]
    - _create_content_string(row, fields) -> str
```

#### **3. VectorStoreManager**  
```python
class VectorStoreManager:
    - setup_embeddings_and_vectorstore(docs) -> Tuple
```

#### **4. QueryProcessor**
```python
class QueryProcessor:
    - extract_documents_from_query(docs, query) -> List[Dict]
    - parse_query_for_fields(query, fields) -> Dict
    - find_matching_documents(docs, criteria) -> List[Dict]
```

#### **5. ResponseProcessor**
```python
class ResponseProcessor:
    - preprocess_df_data(llm_output) -> Dict
    - dict_to_context(data_list, title) -> str
```

#### **6. GapLLM**
```python
class GapLLM(LLM):
    - _call(prompt, stop) -> str
    - _llm_type() -> str
```

### **Backend Responsibilities**
- ✅ **Data Management**: CSV loading, preprocessing, vector store creation
- ✅ **Query Processing**: Route queries, extract relevant documents
- ✅ **LLM Integration**: Gap API communication, prompt management
- ✅ **Response Processing**: Parse LLM outputs, format responses
- ✅ **Session Management**: Maintain conversation state
- ✅ **Token Counting**: Track usage statistics
- ✅ **Error Handling**: Robust error management and logging

---

## 🎨 Frontend Architecture (`nettune_frontend.py`)

### **Core Class**

#### **NetTuneFrontend** (Main UI Controller)
```python
class NetTuneFrontend:
    - run() -> None                           # Main application loop
    - initialize_session_state() -> None      # Setup Streamlit state
    - initialize_backend() -> None            # Connect to backend
    - render_header() -> None                 # Display branding
    - render_sidebar() -> None                # Controls & info panel
    - render_chat_interface() -> None         # Main chat area
    - process_user_input(input) -> None       # Handle user queries
    - start_new_chat() -> None               # Reset session
    - render_footer() -> None                # Display footer info
```

### **Frontend Responsibilities**
- ✅ **UI Rendering**: Streamlit components, layouts, styling
- ✅ **User Interaction**: Input handling, button actions, navigation
- ✅ **State Management**: Session state, chat history, user preferences
- ✅ **Visual Feedback**: Loading animations, status indicators, error messages
- ✅ **Backend Communication**: Clean API calls to backend service
- ✅ **Responsive Design**: Modern CSS, mobile-friendly layouts

---

## 🔌 API Interface Design

### **Clean Separation Pattern**

#### **Frontend → Backend Communication**
```python
# Frontend calls backend methods
result = self.backend.process_query(question, history, df_result)

# Standardized response format
{
    "status": "success|error",
    "response": "...",
    "context_source": "📚 Database Name", 
    "token_count": 150,
    "new_df_result": {...},
    "message": "Error details if applicable"
}
```

#### **No Direct Dependencies**
- Frontend **never** imports pandas, langchain, or FAISS
- Backend **never** imports streamlit or UI components  
- Clean interface through method calls only

---

## 🚀 Benefits of This Architecture

### **🔧 Maintainability**
- **Single Responsibility**: Each class has one clear purpose
- **Loose Coupling**: Frontend and backend can evolve independently
- **Easy Testing**: Backend logic can be unit tested without UI
- **Code Reuse**: Backend can be used by different frontends (CLI, API, etc.)

### **⚡ Performance**
- **Lazy Loading**: Backend components initialize only when needed
- **Caching Strategy**: Streamlit caching for data and vector stores
- **Memory Management**: Efficient session state handling
- **Parallel Processing**: Backend can handle multiple requests

### **🛠️ Extensibility**
- **New Frontends**: Add web API, mobile app, or desktop UI
- **Backend Scaling**: Replace components without touching UI
- **Feature Addition**: Add new query types, databases, or LLMs
- **Configuration**: Easy parameter tuning and environment setup

### **🔒 Security**
- **Separation of Concerns**: UI logic separate from business logic
- **Input Validation**: Backend validates and sanitizes all inputs
- **Error Isolation**: Frontend errors don't crash backend service
- **API Design**: Controlled interface prevents unauthorized access

---

## 🎯 Usage Patterns

### **For Users**
```bash
# Run with separated architecture
streamlit run nettune_frontend.py

# Alternative: Original monolithic version  
streamlit run nettune_ui.py
```

### **For Developers**

#### **Adding New Features**
1. **Backend Changes**: Modify `nettune_backend.py` classes
2. **Frontend Changes**: Update `nettune_frontend.py` UI components
3. **API Updates**: Ensure interface compatibility

#### **Testing**
```python
# Test backend independently
from nettune_backend import NetTuneBackend
backend = NetTuneBackend()
result = backend.process_query("test query", [], None)

# Test frontend with mock backend
# (Mock the backend.process_query method)
```

#### **Extending**
- **New Data Sources**: Add processor classes in backend
- **New UI Components**: Add render methods in frontend  
- **New Query Types**: Extend routing logic in backend
- **New Styling**: Update CSS in frontend

---

## 📊 Performance Considerations

### **Backend Optimization**
- Use `@st.cache_data` for data loading
- Use `@st.cache_resource` for model initialization
- Implement connection pooling for API calls
- Optimize vector store queries

### **Frontend Optimization**  
- Minimize re-renders with proper session state
- Use placeholders for dynamic content
- Implement progressive loading for large responses
- Cache expensive UI computations

---

## 🔮 Future Architecture Plans

### **Potential Enhancements**
1. **Microservices**: Break backend into smaller services
2. **API Gateway**: REST/GraphQL API for external access
3. **Database Integration**: Replace CSV with proper databases
4. **Caching Layer**: Redis for session and query caching
5. **Load Balancing**: Multiple backend instances
6. **Monitoring**: Logging, metrics, and health checks

### **Technology Stack Evolution**
- **Backend**: FastAPI, SQLAlchemy, Celery for async tasks
- **Frontend**: React/Vue.js for web, Flutter for mobile
- **Infrastructure**: Docker, Kubernetes, cloud deployment
- **Monitoring**: Prometheus, Grafana, ELK stack

---

## 🎉 Summary

The separated architecture provides:
- ✅ **Clean Code**: Well-organized, maintainable codebase
- ✅ **Scalability**: Easy to extend and modify
- ✅ **Testing**: Isolated components for better testing
- ✅ **Reusability**: Backend can power multiple interfaces  
- ✅ **Performance**: Optimized caching and resource management
- ✅ **Security**: Proper separation of concerns

This architecture ensures NetTune AI can grow and evolve while maintaining code quality and developer productivity! 