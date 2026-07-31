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
        description="Monitor validation quality, scoring mix, and active outreach from one workspace."
        eyebrow="Dashboard"
        title="Lead pipeline health"
      />

      <Box
        sx={{
          display: "grid",
          gap: 2.25,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", xl: "repeat(4, minmax(0, 1fr))" },
          mb: 2.5
        }}
      >
        {[
          { label: "Total leads", value: dashboard.total, hint: "All imported records" },
          { label: "Hot leads", value: dashboard.hot, hint: "Ready for immediate action" },
          { label: "Warm leads", value: dashboard.warm, hint: "Good nurture candidates" },
          { label: "Active follow-ups", value: dashboard.active_followups, hint: "Automation queue" }
        ].map(({ label, value, hint }) => (
          <MetricCard hint={hint} key={label} label={label} value={value || 0} />
        ))}
      </Box>

      <PanelCard
        action={
          <Button component={Link} href="/leads" size="small" variant="outlined">
            View all
          </Button>
        }
        description="Latest imported records and their routing status."
        title="Recent leads"
      >
        {leads.length ? (
          <TableContainer
            sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflowX: "auto" }}
          >
            <Table sx={{ minWidth: 820 }}>
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
                            {lead.name}
                          </Typography>
                        </Link>
                        <Typography color="text.secondary" variant="body2">
                          {lead.email || "-"}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography>
                        {lead.configuration} {lead.property_type}
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
