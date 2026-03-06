import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import './FileUpload.css';

const API_URL = "http://localhost:8000/api/v1";
const WS_URL = "ws://localhost:8000/api/v1/ws";

const TranscodeCard = () => {
    // States: IDLE, UPLOADING, PROCESSING, COMPLETED, FAILED
    const [viewState, setViewState] = useState('IDLE');
    const [file, setFile] = useState(null);
    const [videoId, setVideoId] = useState(null);
    const [progress, setProgress] = useState(0);
    const [statusText, setStatusText] = useState("");
    const [error, setError] = useState('');
    const [sliceCount, setSliceCount] = useState(5);

    // WebSocket Setup
    const { sendMessage, lastMessage, readyState } = useWebSocket(
        videoId ? `${WS_URL}/${videoId}` : null,
        {
            shouldReconnect: () => true,
            onOpen: () => console.log('WS Connected'),
            onClose: () => console.log('WS Closed'),
        }
    );

    // Handle WebSocket Messages
    useEffect(() => {
        if (lastMessage !== null) {
            const message = lastMessage.data;
            setStatusText(message);

            if (message === "COMPLETED") {
                setProgress(100);
                setViewState('COMPLETED');
            } else if (message === "FAILED") {
                setViewState('FAILED');
                setError("Transcoding failed on server.");
            } else {
                setViewState('PROCESSING');
                const match = message.match(/(\d+)%/);
                if (match) {
                    setProgress(parseInt(match[1]));
                }
            }
        }
    }, [lastMessage]);

    // Memoize the preview URL to prevent video reloading on re-renders
    const previewUrl = useMemo(() => {
        return file ? URL.createObjectURL(file) : null;
    }, [file]);

    // Cleanup object URL
    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        };
    }, [previewUrl]);

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
            setFile(e.target.files[0]);
            setError('');
            // Optional: reset state if re-selecting
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setViewState('UPLOADING');
        setError('');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('target_format', 'mp4');
        formData.append('slice_count', sliceCount);

        try {
            const response = await axios.post(`${API_URL}/upload`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            setVideoId(response.data.video_id);
            // Don't switch to PROCESSING yet, wait for WebSocket/Time
            // But we can stay in UPLOADING until WS connects
        } catch (err) {
            console.error(err);
            setError("Upload failed. Please try again.");
            setViewState('IDLE'); // Recover
        }
    };

    const handleReset = () => {
        setFile(null);
        setVideoId(null);
        setProgress(0);
        setStatusText("");
        setViewState('IDLE');
        setError('');
    };

    const isUploading = viewState === 'UPLOADING';
    const isProcessing = viewState === 'PROCESSING';
    const isCompleted = viewState === 'COMPLETED';

    return (
        <div className="card">
            <h1>Transcode Pro</h1>

            <div className={`upload-area ${file ? 'has-file' : ''}`}>

                {/* File Input (Only clickable in IDLE or has-file but not processing) */}
                <input
                    type="file"
                    id="file-upload"
                    onChange={handleFileChange}
                    accept="video/*"
                    disabled={viewState !== 'IDLE'}
                    style={{ display: 'none' }}
                />

                {!file && viewState === 'IDLE' && (
                    <div className="upload-container">
                        <label htmlFor="file-upload" className="upload-label">
                            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>📁</div>
                            <p>Click to browse or drag video here</p>
                        </label>
                    </div>
                )}

                {file && (
                    <div className="preview-container">
                        <video
                            src={previewUrl}
                            className="preview-video"
                            controls={false}
                            muted
                            autoPlay={isUploading}
                            loop
                        />

                        {/* Slice Controls Overlay - Only valid when IDLE (File selected but not uploading) */}
                        {viewState === 'IDLE' && (
                            <div className="slice-overlay-controls">
                                <div className="slice-control">
                                    <label>Slices: {sliceCount}</label>
                                    <input
                                        type="range"
                                        min="3"
                                        max="8"
                                        value={sliceCount}
                                        onChange={(e) => setSliceCount(parseInt(e.target.value))}
                                    />
                                    <p className="est-time">Est. Time: ~{Math.round(60 / sliceCount)}s</p>
                                </div>
                            </div>
                        )}

                        {/* Animation Overlay: Visible during Uploading AND Processing */}
                        {(isUploading || isProcessing) && !isCompleted && (
                            <div className="slicing-overlay">
                                <div className="slice-container">
                                    {Array.from({ length: sliceCount }).map((_, index) => (
                                        <div
                                            key={index}
                                            className="slice"
                                        // Synchronized animation: no delay, no random duration
                                        ></div>
                                    ))}
                                </div>
                                <div className="uploading-icon">☁️⬆️</div>
                            </div>
                        )}

                        {/* Success Overlay */}
                        {isCompleted && (
                            <div className="success-overlay">
                                <div className="success-icon">✅</div>
                            </div>
                        )}

                        <p className="status-text">
                            {isCompleted ? "Transcoding Complete!" : `Selected: ${file.name}`}
                        </p>
                    </div>
                )}
            </div>

            {/* Action Area */}
            {viewState === 'IDLE' && (
                <button onClick={handleUpload} disabled={!file}>
                    🚀 Upload & Transcode
                </button>
            )}

            {(isUploading || isProcessing) && (
                <div className="progress-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                        <span>{statusText || "Initializing..."}</span>
                        <span>{progress}%</span>
                    </div>
                    <div className="progress-bar-container">
                        <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
                    </div>
                </div>
            )}

            {isCompleted && (
                <div className="completion-actions">
                    <button className="download-btn" disabled>Download Video (Mock)</button>
                    <button className="reset-btn" onClick={handleReset}>Transcode Another File</button>
                </div>
            )}

            {error && <p className="error-message">{error}</p>}
        </div>
    );
};

export default TranscodeCard;
