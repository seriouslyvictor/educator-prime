import { api } from "./api";
import type { ExportFile, ExportJob } from "../types";

export function isFolderExportSupported(): boolean {
  return typeof window.showDirectoryPicker === "function";
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
    throw new Error(`Invalid output path: ${file.output_path}`);
  }

  const directory = await ensureDirectory(root, parts);
  const handle = await directory.getFileHandle(filename, { create: true });
  const writable = await handle.createWritable();
  const response = await fetch(api.fileUrl(jobId, file.id));
  if (!response.ok || !response.body) {
    throw new Error(`Failed to download ${file.output_path}`);
  }
  await writable.write(await response.blob());
  await writable.close();
}

export async function exportJobToFolder(
  job: ExportJob,
  onProgress: (completed: number, total: number, currentPath: string) => void,
): Promise<void> {
  if (!window.showDirectoryPicker) {
    throw new Error("Folder export requires Chrome or Edge.");
  }

  const root = await window.showDirectoryPicker({
    id: "classroom-downloader-export",
    mode: "readwrite",
  });

  let completed = 0;
  for (const file of job.files) {
    await writeExportFile(root, job.id, file);
    completed += 1;
    onProgress(completed, job.files.length, file.output_path);
  }
}
