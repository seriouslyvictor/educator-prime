import type { Activity, Course, ExportJob } from "../types";

export type PreviewTreeNode = {
  name: string;
  type: "dir" | "file" | "note";
  children?: PreviewTreeNode[];
};

export function buildPreviewTree(
  course: Course,
  activities: Activity[],
  job?: ExportJob | null,
): PreviewTreeNode {
  if (job?.files.length) {
    const root: PreviewTreeNode = { name: course.name, type: "dir", children: [] };
    for (const file of job.files.slice(0, 80)) {
      const parts = file.output_path.split("/");
      let cursor = root;
      for (const [index, part] of parts.entries()) {
        const isFile = index === parts.length - 1;
        cursor.children ??= [];
        let next = cursor.children.find((child) => child.name === part);
        if (!next) {
          next = { name: part, type: isFile ? "file" : "dir", children: isFile ? undefined : [] };
          cursor.children.push(next);
        }
        cursor = next;
      }
    }
    if (job.files.length > 80) {
      root.children?.push({ name: `and ${job.files.length - 80} more files`, type: "note" });
    }
    return root;
  }

  return {
    name: course.name,
    type: "dir",
    children: activities.map((activity) => ({
      name: activity.title,
      type: "dir",
      children: [{ name: "Files resolved after export starts", type: "note" }],
    })),
  };
}
