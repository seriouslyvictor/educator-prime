import { api } from "./api";
import type { ExportFile, ExportJob } from "../types";

export type ExportFolderSummary = {
  completed: number;
  failed: Array<{ path: string; reason: string }>;
};

export function isFolderExportSupported(): boolean {
  return typeof window.showDirectoryPicker === "function";
}

export async function pickExportFolder(): Promise<FileSystemDirectoryHandle> {
  if (!window.showDirectoryPicker) {
    throw new Error("A exportação para pasta exige Chrome ou Edge.");
  }

  return window.showDirectoryPicker({
    id: "classroom-downloader-export",
    mode: "readwrite",
  });
}

async function ensureDirectory(
  root: FileSystemDirectoryHandle,
  segments: string[],
): Promise<FileSystemDirectoryHandle> {
  let current = root;
  for (const segment of segments) {
    current = await current.getDirectoryHandle(segment, { create: true });
  }
  return current;
}

async function writeExportFile(
  root: FileSystemDirectoryHandle,
  jobId: string,
  file: ExportFile,
): Promise<void> {
  const parts = file.output_path.split("/");
  const filename = parts.pop();
  if (!filename) {
    throw new Error(`Caminho de saída inválido: ${file.output_path}`);
  }

  const directory = await ensureDirectory(root, parts);
  const handle = await directory.getFileHandle(filename, { create: true });
  const writable = await handle.createWritable();
  const response = await fetch(api.fileUrl(jobId, file.id));
  if (!response.ok || !response.body) {
    throw new Error(`Falha ao baixar ${file.output_path}`);
  }
  await writable.write(await response.blob());
  await writable.close();
}

function isFatalExportError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === "NotAllowedError" || error.name === "QuotaExceededError";
  }
  return false;
}

function errorReason(error: unknown): string {
  return error instanceof Error ? error.message : "Falha ao baixar o arquivo.";
}

export async function exportJobToFolder(
  job: ExportJob,
  root: FileSystemDirectoryHandle,
  onProgress: (completed: number, total: number, currentPath: string) => void,
): Promise<ExportFolderSummary> {
  let completed = 0;
  const failed: ExportFolderSummary["failed"] = [];
  for (const file of job.files) {
    try {
      await writeExportFile(root, job.id, file);
      completed += 1;
      onProgress(completed, job.files.length, file.output_path);
    } catch (error) {
      if (isFatalExportError(error)) throw error;
      failed.push({ path: file.output_path, reason: errorReason(error) });
      onProgress(completed, job.files.length, `Falhou: ${file.output_path}`);
    }
  }
  return { completed, failed };
}
