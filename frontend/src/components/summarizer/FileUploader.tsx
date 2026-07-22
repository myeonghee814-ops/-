import { useRef, useState } from "react";
import type { DragEvent } from "react";
import { UploadCloud } from "lucide-react";
import { MAX_PAPERS } from "../../types/summarizer";

interface FileUploaderProps {
  currentCount: number;
  disabled?: boolean;
  onFilesAdded: (files: File[]) => void;
}

export function FileUploader({ currentCount, disabled, onFilesAdded }: FileUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const remaining = MAX_PAPERS - currentCount;
  const isDisabled = disabled || remaining <= 0;

  function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;

    const incoming = Array.from(fileList).filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    const rejectedNonPdf = fileList.length - incoming.length;

    const accepted = incoming.slice(0, remaining);
    const rejectedOverLimit = incoming.length - accepted.length;

    if (rejectedNonPdf > 0 || rejectedOverLimit > 0) {
      const parts: string[] = [];
      if (rejectedNonPdf > 0) parts.push(`PDF가 아닌 파일 ${rejectedNonPdf}개는 제외했습니다`);
      if (rejectedOverLimit > 0) parts.push(`최대 ${MAX_PAPERS}개 제한으로 ${rejectedOverLimit}개는 추가되지 않았습니다`);
      setWarning(parts.join(", ") + ".");
    } else {
      setWarning(null);
    }

    if (accepted.length > 0) onFilesAdded(accepted);
  }

  return (
    <div>
      <div
        onDragOver={(e: DragEvent) => {
          e.preventDefault();
          if (!isDisabled) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e: DragEvent) => {
          e.preventDefault();
          setIsDragging(false);
          if (!isDisabled) handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !isDisabled && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
          isDisabled ? "cursor-not-allowed border-border opacity-50" : "cursor-pointer border-border hover:border-primary/50"
        } ${isDragging ? "border-primary bg-primary/5" : "bg-transparent"}`}
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <UploadCloud className="size-6" />
        </div>
        <p className="mt-4 text-[15px] font-medium text-text">PDF를 드래그하거나 클릭하여 업로드</p>
        <p className="mt-1.5 text-xs text-subtext">
          {currentCount} / {MAX_PAPERS}개 업로드됨
        </p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          disabled={isDisabled}
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {warning && <p className="mt-2 text-xs text-amber-600">{warning}</p>}
    </div>
  );
}
