import { apiGet, Lead } from "@/lib/api";
import Link from "next/link";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import {
  Box,
  Button,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { EmptyState, MetricCard, PageHeader, PanelCard, ScoreChip } from "./ui";

type Dashboard = {
  total: number;
  hot: number;
  warm: number;
  cold: number;
  valid_emails: number;
  valid_phones: number;
  active_followups: number;
  responded: number;
};

export default async function DashboardPage() {
  const [dashboard, leads] = await Promise.all([
    apiGet<Dashboard>("/dashboard").catch(() => ({
      total: 0,
      hot: 0,
      warm: 0,
      cold: 0,
      valid_emails: 0,
      valid_phones: 0,
      active_followups: 0,
      responded: 0
    })),
    apiGet<Lead[]>("").catch(() => [])
  ]);

  return (
    <>
      <PageHeader
        action={
          <Button component={Link} href="/upload" startIcon={<FileUploadOutlinedIcon />} variant="contained">
            Upload Leads
          </Button>
        }
        description="Track lead volume, priority mix, validation quality, and follow-up activity."
        eyebrow="Dashboard"
        title="Lead Pipeline"
      />

      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(4, minmax(0, 1fr))" },
          mb: 2
        }}
      >
        {[
          { label: "Total Leads", value: dashboard.total, hint: "Imported records" },
          { label: "Hot Leads", value: dashboard.hot, hint: "Ready for agent action" },
          { label: "Warm Leads", value: dashboard.warm, hint: "In nurture queue" },
          { label: "Pending Follow-Ups", value: dashboard.active_followups, hint: "Active automation" }
        ].map(({ label, value, hint }) => (
          <MetricCard hint={hint} key={label} label={label} value={value || 0} />
        ))}
      </Box>

      <PanelCard
        action={
          <Button component={Link} href="/leads" size="small" variant="outlined">
            View All
          </Button>
        }
        description="Latest imported leads with score, category, and owner."
        title="Recent Leads"
      >
        {leads.length ? (
          <TableContainer
            sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflowX: "auto" }}
          >
            <Table size="small" sx={{ minWidth: 820 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Interest</TableCell>
                  <TableCell>Score</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Agent</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {leads.slice(0, 8).map((lead) => (
                  <TableRow hover key={lead.id}>
                    <TableCell>
                      <Stack spacing={0.35}>
                        <Link href={`/leads/${lead.id}`}>
                          <Typography color="text.primary" component="span" sx={{ fontWeight: 800 }}>
                            {formatDisplayName(lead.name)}
                          </Typography>
                        </Link>
                        <Typography color="text.secondary" variant="body2">
                          {lead.email || "-"}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ fontWeight: 750 }}>
                        {formatDisplayName(`${lead.configuration || ""} ${lead.property_type || ""}`) || "Property Requirement"}
                      </Typography>
                      <Typography color="text.secondary" variant="body2">
                        {lead.location_preference || "Any location"}
                      </Typography>
                    </TableCell>
                    <TableCell>{lead.score}</TableCell>
                    <TableCell>
                      <ScoreChip band={lead.score_band} />
                    </TableCell>
                    <TableCell>{lead.assigned_agent_name || "Unassigned"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <EmptyState title="No leads imported yet" description="Upload a CSV or Excel file to start validation and scoring." />
        )}
      </PanelCard>
    </>
  );
}

function formatDisplayName(value?: string) {
  const clean = String(value || "").replace(/[_-]+/g, " ").trim();
  if (!clean) {
    return "";
  }
  return clean
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
