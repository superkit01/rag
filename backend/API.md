# RAG Backend API Documentation

## Sessions API

### POST /api/sessions
Create a new session.
- Body: `{ knowledge_space_id: string, name?: string }`
- Response: Session object with id, name, knowledge_space_id, created_at, updated_at

### GET /api/sessions?knowledge_space_id={id}
List sessions for a knowledge space.
- Query: knowledge_space_id (optional)
- Response: Array of Session objects

### GET /api/sessions/{id}
Get session details.
- Response: Session object

### GET /api/sessions/{id}/traces
Get all answer traces for a session.
- Response: Array of AnswerTrace objects

### PATCH /api/sessions/{id}
Update session name or timestamp.
- Body: `{ name?: string }`
- Response: Updated Session object

## Other Endpoints

### /api/health
Health check endpoint.

### /api/queries/answer
Submit a question and get an answer.

### /api/documents
Document management endpoints.

See code for full API reference.
