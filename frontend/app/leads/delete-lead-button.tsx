"use client";

import { useState } from "react";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import { Button } from "@mui/material";
import { useRouter } from "next/navigation";
import { apiDelete } from "@/lib/api";

export default function DeleteLeadButton({ leadId, leadName }: { leadId: number; leadName: string }) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);

  async function deleteLead() {
    const confirmed = window.confirm(
      `Delete ${leadName || `lead #${leadId}`}? This also removes related call, message, and email learning logs.`
    );
    if (!confirmed) {
      return;
    }

    setDeleting(true);
    try {
      await apiDelete(`/${leadId}`);
      router.refresh();
    } catch (error) {
      window.alert(error instanceof Error ? error.message : "Lead deletion failed.");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <Button
      color="error"
      disabled={deleting}
      onClick={deleteLead}
      size="small"
      startIcon={<DeleteOutlineOutlinedIcon />}
      variant="text"
    >
      {deleting ? "Deleting" : "Delete"}
    </Button>
  );
}
