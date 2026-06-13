import { afterEach, describe, expect, it, vi } from "vitest";
import { exportJobToFolder } from "./folder-export";
import type { ExportFile, ExportJob } from "../types";

type FakeWritable = {
  write: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
};

type FakeDirectory = {
  getDirectoryHandle: ReturnType<typeof vi.fn>;
  getFileHandle: ReturnType<typeof vi.fn>;
  writables: FakeWritable[];
};

function exportFile(id: string, outputPath: string): ExportFile {
  return {
    id,
    activity_id: "activity-1",
    activity_name: "Activity",
    student_email: null,
    student_name: null,
    source_name: `${id}.pdf`,
    mime_type: "application/pdf",
    export_mime_type: null,
    output_path: outputPath,
    status: "ready",
    error: null,
  };
}

function exportJob(files: ExportFile[]): ExportJob {
  return {
    id: "job-1",
    course_id: "course-1",
    course_name: "Course",
    status: "completed",
    total_files: files.length,
    completed_files: files.length,
    files,
    errors: [],
  };
}

function fakeDir(options: { writeError?: unknown } = {}): FakeDirectory {
  const dir: FakeDirectory = {
    getDirectoryHandle: vi.fn(async () => fakeDir(options)),
    getFileHandle: vi.fn(async () => {
      const writable: FakeWritable = {
        write: vi.fn(async () => {
          if (options.writeError) throw options.writeError;
        }),
        close: vi.fn(async () => {}),
      };
      dir.writables.push(writable);
      return {
        createWritable: vi.fn(async () => writable),
      };
    }),
    writables: [],
  };
  return dir;
}

function okDownload(): Response {
  return {
    ok: true,
    body: {},
    blob: async () => new Blob(["file"]),
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("exportJobToFolder", () => {
  it("writes every file and reports progress", async () => {
    const fetch = vi.fn().mockResolvedValue(okDownload());
    vi.stubGlobal("fetch", fetch);
    const progress = vi.fn();
    const root = fakeDir();

    const summary = await exportJobToFolder(
      exportJob([exportFile("file-1", "A/one.pdf"), exportFile("file-2", "B/two.pdf")]),
      root as unknown as FileSystemDirectoryHandle,
      progress,
    );

    expect(summary).toEqual({ completed: 2, failed: [] });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(progress).toHaveBeenNthCalledWith(1, 1, 2, "A/one.pdf");
    expect(progress).toHaveBeenNthCalledWith(2, 2, 2, "B/two.pdf");
  });

  it("collects per-file failures and continues", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(okDownload())
      .mockResolvedValueOnce({ ok: false, body: {}, blob: async () => new Blob() })
      .mockResolvedValueOnce(okDownload());
    vi.stubGlobal("fetch", fetch);
    const progress = vi.fn();

    const summary = await exportJobToFolder(
      exportJob([
        exportFile("file-1", "A/one.pdf"),
        exportFile("file-2", "A/two.pdf"),
        exportFile("file-3", "A/three.pdf"),
      ]),
      fakeDir() as unknown as FileSystemDirectoryHandle,
      progress,
    );

    expect(summary.completed).toBe(2);
    expect(summary.failed).toEqual([{ path: "A/two.pdf", reason: "Falha ao baixar A/two.pdf" }]);
    expect(progress).toHaveBeenCalledWith(1, 3, "Falhou: A/two.pdf");
    expect(progress).toHaveBeenLastCalledWith(2, 3, "A/three.pdf");
  });

  it("aborts on fatal export errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okDownload()));
    const progress = vi.fn();

    await expect(
      exportJobToFolder(
        exportJob([exportFile("file-1", "A/one.pdf"), exportFile("file-2", "A/two.pdf")]),
        fakeDir({ writeError: new DOMException("nope", "NotAllowedError") }) as unknown as FileSystemDirectoryHandle,
        progress,
      ),
    ).rejects.toMatchObject({ name: "NotAllowedError" });

    expect(progress).not.toHaveBeenCalled();
  });

  it("records empty output filenames as per-file failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(okDownload()));
    const progress = vi.fn();

    const summary = await exportJobToFolder(
      exportJob([exportFile("file-1", "folder/")]),
      fakeDir() as unknown as FileSystemDirectoryHandle,
      progress,
    );

    expect(summary.completed).toBe(0);
    expect(summary.failed[0]?.path).toBe("folder/");
    expect(summary.failed[0]?.reason).toContain("folder/");
    expect(summary.failed[0]?.reason).toContain("Caminho");
    expect(progress).toHaveBeenCalledWith(0, 1, "Falhou: folder/");
  });
});
