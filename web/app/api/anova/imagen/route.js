import fs from "fs/promises";
import path from "path";

const ALLOWED = /^anova_[\w]+\.png$/;

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const filename = searchParams.get("f") ?? "";

  if (!ALLOWED.test(filename)) {
    return new Response("Not found", { status: 404 });
  }

  try {
    const filePath = path.resolve(process.cwd(), "..", "data", "quality_reports", filename);
    const data = await fs.readFile(filePath);
    return new Response(data, {
      headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=3600" },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
