import { ReactNode } from "react";
import { Box, Card, CardContent, Chip, Stack, Typography } from "@mui/material";
import type { SxProps, Theme } from "@mui/material/styles";

const scoreStyles = {
  Hot: { bgcolor: "#fee8df", color: "#9b3d14" },
  Warm: { bgcolor: "#fff1c7", color: "#765400" },
  Cold: { bgcolor: "#e8edf5", color: "#42526a" }
};

const validationStyles = {
  Valid: { bgcolor: "#dff5ea", color: "#0f7a55" },
  Invalid: { bgcolor: "#fde8e5", color: "#bf3b32" },
  Duplicate: { bgcolor: "#eef2f7", color: "#42526a" },
  Pending: { bgcolor: "#eef2f7", color: "#42526a" }
};

export function PageHeader({
  eyebrow,
  title,
  description,
  action
}: {
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <Stack
      direction={{ xs: "column", sm: "row" }}
      spacing={1.5}
      sx={{ alignItems: { xs: "stretch", sm: "flex-start" }, justifyContent: "space-between", mb: 2.25 }}
    >
      <Box>
        <Typography
          color="primary.dark"
          sx={{ fontSize: 11, fontWeight: 900, lineHeight: 1.2, textTransform: "uppercase" }}
        >
          {eyebrow}
        </Typography>
        <Typography component="h1" variant="h1" sx={{ mt: 0.65 }}>
          {title}
        </Typography>
        {description ? (
          <Typography color="text.secondary" sx={{ fontSize: 14, maxWidth: 760, mt: 0.65 }}>
            {description}
          </Typography>
        ) : null}
      </Box>
      {action ? <Box>{action}</Box> : null}
    </Stack>
  );
}

export function PanelCard({
  title,
  description,
  icon,
  action,
  children,
  sx
}: {
  title?: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  sx?: SxProps<Theme>;
}) {
  return (
    <Card sx={sx}>
      <CardContent sx={{ p: { xs: 1.5, sm: 1.75 }, "&:last-child": { pb: { xs: 1.5, sm: 1.75 } } }}>
        {title || description || icon || action ? (
          <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start", justifyContent: "space-between", mb: 1.35 }}>
            <Box sx={{ minWidth: 0 }}>
              {title ? (
                <Typography component="h2" variant="h2">
                  {title}
                </Typography>
              ) : null}
              {description ? (
                <Typography color="text.secondary" sx={{ fontSize: 13.5, mt: 0.35 }}>
                  {description}
                </Typography>
              ) : null}
            </Box>
            {action || icon ? <Box sx={{ flex: "0 0 auto" }}>{action || icon}</Box> : null}
          </Stack>
        ) : null}
        {children}
      </CardContent>
    </Card>
  );
}

export function MetricCard({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <Card sx={{ overflow: "hidden", position: "relative" }}>
      <Box sx={{ bgcolor: "primary.main", height: 3 }} />
      <CardContent sx={{ p: 1.45, "&:last-child": { pb: 1.45 } }}>
        <Typography color="text.primary" sx={{ fontSize: 24, fontWeight: 900, lineHeight: 1.05 }}>
          {value}
        </Typography>
        <Typography color="text.secondary" sx={{ fontSize: 12.5, fontWeight: 850, mt: 0.6 }}>
          {label}
        </Typography>
        {hint ? (
          <Typography color="text.secondary" sx={{ fontSize: 11.5, mt: 0.45 }}>
            {hint}
          </Typography>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <Stack
      spacing={0.5}
      sx={{
        alignItems: "center",
        bgcolor: "#f9fbfd",
        border: "1px dashed",
        borderColor: "divider",
        borderRadius: 2,
        color: "text.secondary",
        minHeight: 112,
        p: 2.2,
        justifyContent: "center",
        textAlign: "center"
      }}
    >
      <Typography color="text.primary" sx={{ fontWeight: 850 }}>
        {title}
      </Typography>
      <Typography>{description}</Typography>
    </Stack>
  );
}

export function ScoreChip({ band }: { band?: "Hot" | "Warm" | "Cold" | string | null }) {
  const safeBand = band === "Hot" || band === "Warm" || band === "Cold" ? band : "Cold";
  return <Chip label={safeBand} size="small" sx={{ ...scoreStyles[safeBand], fontWeight: 850 }} />;
}

export function ValidationChip({ status }: { status?: "Valid" | "Invalid" | "Duplicate" | "Pending" | string | null }) {
  const safeStatus =
    status === "Valid" || status === "Invalid" || status === "Duplicate" || status === "Pending" ? status : "Pending";
  return <Chip label={safeStatus} size="small" sx={{ ...validationStyles[safeStatus], fontWeight: 850 }} />;
}

export function EmailStatusChip({ status }: { status?: string }) {
  const sent = status === "sent";
  return (
    <Chip
      label={sent ? "Sent" : "Not Sent"}
      size="small"
      sx={{
        bgcolor: sent ? "#dff5ea" : "#eef2f7",
        color: sent ? "#0f7a55" : "#42526a",
        fontWeight: 850
      }}
    />
  );
}

export function DraftStatusChip({ ready }: { ready?: boolean }) {
  return (
    <Chip
      label={ready ? "Draft Ready" : "No Draft"}
      size="small"
      sx={{
        bgcolor: ready ? "#e5f7ef" : "#eef2f7",
        color: ready ? "#0f7a55" : "#42526a",
        fontWeight: 850
      }}
    />
  );
}
