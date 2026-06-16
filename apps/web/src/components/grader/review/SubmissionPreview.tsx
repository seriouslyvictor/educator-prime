import { useEffect, useState } from "react";
import { api } from "../../../lib/api";
import { AppIcon } from "../../icons";
import { studentLabel } from "../domain";
import { errorLayerLabel, safeStatusLabel } from "../graderStatus";
import type { GradingJob, GradingSubmission, GradingSubmissionFile } from "../../../types";

// Mirror the backend's inline allowlist: only types it serves with
// `Content-Disposition: inline` are embedded; everything else is a download card.
const INLINE_IMAGE_MIME = new Set(["image/png", "image/jpeg", "image/gif", "image/webp"]);
const INLINE_TEXT_MIME = new Set([
  "text/plain",
  "text/csv",
  "text/markdown",
  "text/x-python",
  "text/x-java-source",
  "text/x-c",
  "text/x-c++",
  "text/x-csharp",
  "text/x-go",
  "text/x-rust",
  "text/x-php",
  "text/x-ruby",
  "text/x-sql",
  "application/json",
  "application/ld+json",
  "application/xml",
  "application/xhtml+xml",
  "application/javascript",
  "application/typescript",
  "application/x-yaml",
  "application/yaml",
]);
const INLINE_TEXT_EXTENSIONS = new Set([
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".xml",
  ".yaml",
  ".yml",
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".css",
  ".scss",
  ".html",
  ".htm",
  ".java",
  ".c",
  ".h",
  ".cpp",
  ".hpp",
  ".cs",
  ".go",
  ".rs",
  ".php",
  ".rb",
  ".sql",
  ".sh",
  ".ps1",
  ".bat",
  ".ini",
  ".toml",
  ".lock",
]);

function extensionOf(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function isInlineTextSubmission(sourceName: string, mime: string): boolean {
  if (mime.startsWith("text/") || INLINE_TEXT_MIME.has(mime)) return true;
  return mime === "application/octet-stream" && INLINE_TEXT_EXTENSIONS.has(extensionOf(sourceName));
}

// A student's submission may carry several attachments; show one tab per file.
export function SubmissionFiles({ job, submission }: { job: GradingJob; submission: GradingSubmission }) {
  const files: GradingSubmissionFile[] = submission.files?.length
    ? submission.files
    : [{ source_file_id: submission.source_file_id, source_name: submission.source_name, mime_type: submission.mime_type }];
  const [activeFileId, setActiveFileId] = useState(files[0].source_file_id);
  useEffect(() => {
    setActiveFileId(files[0].source_file_id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submission.id]);
  const activeFile = files.find((file) => file.source_file_id === activeFileId) ?? files[0];

  return (
    <>
      {files.length > 1 ? (
        <div className="file-tabs" role="tablist" aria-label="Arquivos da entrega">
          {files.map((file) => (
            <button
              key={file.source_file_id}
              role="tab"
              aria-selected={file.source_file_id === activeFile.source_file_id}
              className={`file-tab ${file.source_file_id === activeFile.source_file_id ? "active" : ""}`}
              onClick={() => setActiveFileId(file.source_file_id)}
            >
              <AppIcon name="fileText" /> {file.source_name}
            </button>
          ))}
        </div>
      ) : null}
      <SubmissionPreview job={job} submission={submission} file={activeFile} />
    </>
  );
}

function SubmissionPreview({
  job,
  submission,
  file,
}: {
  job: GradingJob;
  submission: GradingSubmission;
  file: GradingSubmissionFile;
}) {
  const url = api.submissionPreviewUrl(job.id, submission.id, file.source_file_id);
  const mime = (file.mime_type ?? "").split(";")[0].trim().toLowerCase();
  const title = `Entrega de ${studentLabel(submission)}`;

  if (INLINE_IMAGE_MIME.has(mime)) {
    return (
      <div className="preview-media">
        <img className="preview-image" src={url} alt={title} />
      </div>
    );
  }
  if (isInlineTextSubmission(file.source_name, mime)) {
    return <SubmissionTextPreview url={url} title={title} fileName={file.source_name} mimeType={file.mime_type} />;
  }
  if (mime === "application/pdf") {
    return <iframe className="preview-frame" src={url} title={title} />;
  }
  return (
    <div className="preview-card">
      <AppIcon name="fileText" />
      <div className="preview-card-copy">
        <strong>{file.source_name}</strong>
        <span>{file.mime_type || "arquivo"}</span>
      </div>
      <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
        <AppIcon name="download" /> Baixar original
      </a>
    </div>
  );
}

function SubmissionTextPreview({
  url,
  title,
  fileName,
  mimeType,
}: {
  url: string;
  title: string;
  fileName: string;
  mimeType: string;
}) {
  const [state, setState] = useState<{ loading: boolean; content: string; error: string | null }>({
    loading: true,
    content: "",
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, content: "", error: null });
    fetch(url)
      .then((response) => {
        if (!response.ok) throw new Error("Falha ao carregar a previsualização.");
        return response.text();
      })
      .then((content) => {
        if (!cancelled) setState({ loading: false, content, error: null });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            loading: false,
            content: "",
            error: error instanceof Error ? error.message : "Falha ao carregar a previsualização.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  return (
    <div className="preview-code" aria-label={title}>
      <div className="preview-code-toolbar">
        <div className="preview-code-copy">
          <strong>{fileName}</strong>
          <span>{mimeType || "texto"}</span>
        </div>
        <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
          <AppIcon name="download" /> Baixar original
        </a>
      </div>
      {state.loading ? (
        <div className="preview-code-state">
          <AppIcon name="loader" className="ico spin" /> Carregando previsualização
        </div>
      ) : state.error ? (
        <div className="preview-code-state danger">
          <AppIcon name="triangleAlert" /> {state.error}
        </div>
      ) : (
        <pre className="preview-code-body">
          <code>{state.content}</code>
        </pre>
      )}
    </div>
  );
}

export function BlockedEvidence({
  jobId,
  submission,
  busy,
  onRetry,
}: {
  jobId: string;
  submission: GradingSubmission;
  busy: boolean;
  onRetry: () => void;
}) {
  const url = api.submissionPreviewUrl(jobId, submission.id);
  return (
    <div className="preview-blocked">
      <AppIcon name="triangleAlert" />
      <h2>Esta entrega não pôde ser lida pela IA</h2>
      <p>
        {submission.error ? (
          <>
            <span className="error-layer">{errorLayerLabel(submission.error)}</span>: {safeStatusLabel(submission.error)}.{" "}
          </>
        ) : null}
        Você ainda pode abrir o arquivo original
        {submission.error_retryable ? ", tentar novamente" : ""} ou dar uma nota manual no painel ao lado.
      </p>
      <div className="preview-blocked-actions">
        <a className="btn btn-secondary" href={url} target="_blank" rel="noreferrer">
          <AppIcon name="download" /> Baixar original
        </a>
        {submission.error_retryable ? (
          <button className="btn btn-ai" onClick={onRetry} disabled={busy}>
            <AppIcon name={busy ? "loader" : "refresh"} className={busy ? "ico spin" : "ico"} />
            Tentar novamente
          </button>
        ) : null}
      </div>
    </div>
  );
}
