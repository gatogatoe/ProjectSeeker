# Optional assistant

The library, search, collections, and player work without an assistant. Project Seeker does not download or start a model automatically.

## Connect a model

Open Settings > Assistant and choose a local model server or an OpenAI-compatible API. Enter the endpoint, model name, and an API key if required. Remote endpoints require HTTPS; HTTP is accepted only for localhost. Reasoning controls are optional and depend on the selected provider and model.

## Choose a mode

- **Normal chat:** sends your message and permitted conversation history without attaching library metadata.
- **Search projects:** turns your request into validated filters, searches the indexed library, and describes actual matches. Up to 12 project results are sent with the total match count.
- **Create:** suggests musical ideas and titles, using selected-project metadata when applicable and permitted. It does not create files or projects.
- **My Wrapped:** summarizes projects or in-app listening. Choose projects, listening, or both before sending. A date range filters projects by creation or last modification date; listening counts remain all-time.

“Ask the assistant” in project details starts a new chat in Create mode with that project selected. You can remove the project context. The model receives metadata, never audio, and cannot listen to the beat.

Responses can stream progressively. Stop generation disconnects the request and retains visible partial text; whether remote computation stops depends on the provider. Editing a user message replaces it and removes later messages before generating a new response. Responses follow the current app language unless you explicitly request another language.

## Privacy

Typed messages go to the configured provider. Sending library information to an external provider requires separate consent. Without that consent, requests exclude library metadata and conversation history. With consent, relevant data may include project names and paths, notes, tags, BPM, plugins, dates, FL hours, and listening summaries. Audio and sample contents are never sent.

An entirely local model can process library data locally. A localhost proxy may forward requests elsewhere; the Cloud/Local label does not prove where inference runs. Check the server you configure.

Windows API keys are encrypted for your Windows account using DPAPI. Conversations are stored locally without encryption in `%APPDATA%\ProjectSeeker\chat.json` and can contain project names and paths. Delete conversations from the assistant screen when no longer needed.

## Data and response limitations

FL hours come from project files rather than measured work sessions and may be repeated across copies. Ableton does not provide this value. In-app listening counts begin after 30 seconds of playback and exclude DAWs and external players. The stored count and last-played date cannot reconstruct annual listening history. Period-filtered projects describe their current file metadata, not a complete history of work during that period.

Model responses can be inaccurate. File actions use current library records; model-generated paths do not become actions. Support for a compatible API does not guarantee every provider's streaming, reasoning, or model behavior.
