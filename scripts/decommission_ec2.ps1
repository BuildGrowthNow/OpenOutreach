[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory = $true)]
    [string]$EvidenceFile,
    [Parameter(Mandatory = $true)]
    [string]$ConfirmInstanceId,
    [switch]$ReleaseElasticIp
)

$ErrorActionPreference = 'Stop'
$ExpectedInstanceId = 'i-027c586e0728aaded'
$ExpectedName = 'Linkedin-auth'
$ExpectedIp = '50.19.251.160'
$ExpectedAllocationId = 'eipalloc-02e6bfaa77ead1673'
$ExpectedVolumeId = 'vol-0d7f16cbe367284fd'
$Region = 'us-east-1'

if ($ConfirmInstanceId -cne $ExpectedInstanceId) {
    throw "Refusing decommission: exact confirmation must be $ExpectedInstanceId"
}
if (-not (Test-Path -LiteralPath $EvidenceFile -PathType Leaf)) {
    throw "Refusing decommission: evidence file does not exist"
}
$evidence = Get-Item -LiteralPath $EvidenceFile
if ($evidence.LastWriteTimeUtc -lt [DateTime]::UtcNow.AddHours(-24)) {
    throw "Refusing decommission: evidence must be less than 24 hours old"
}

$instance = aws ec2 describe-instances --region $Region --instance-ids $ExpectedInstanceId --output json | ConvertFrom-Json
$item = $instance.Reservations[0].Instances[0]
$name = ($item.Tags | Where-Object Key -eq 'Name').Value
if ($item.InstanceId -cne $ExpectedInstanceId -or $name -cne $ExpectedName) {
    throw "Refusing decommission: instance identity/tag mismatch"
}
$root = $item.BlockDeviceMappings | Where-Object DeviceName -eq $item.RootDeviceName
if ($root.Ebs.VolumeId -cne $ExpectedVolumeId -or -not $root.Ebs.DeleteOnTermination) {
    throw "Refusing decommission: root volume identity or DeleteOnTermination mismatch"
}
$address = aws ec2 describe-addresses --region $Region --allocation-ids $ExpectedAllocationId --output json | ConvertFrom-Json
$address = $address.Addresses[0]
if ($address.PublicIp -cne $ExpectedIp -or $address.InstanceId -cne $ExpectedInstanceId) {
    throw "Refusing decommission: Elastic IP identity/association mismatch"
}

if ($PSCmdlet.ShouldProcess($ExpectedInstanceId, 'Terminate exact EC2 instance')) {
    aws ec2 terminate-instances --region $Region --instance-ids $ExpectedInstanceId | Out-Null
    aws ec2 wait instance-terminated --region $Region --instance-ids $ExpectedInstanceId
}

$volumeCheck = aws ec2 describe-volumes --region $Region --volume-ids $ExpectedVolumeId 2>&1
if ($LASTEXITCODE -eq 0) {
    throw "Cleanup exception: expected root volume $ExpectedVolumeId still exists"
}

if ($ReleaseElasticIp -and $PSCmdlet.ShouldProcess($ExpectedAllocationId, 'Release exact Elastic IP allocation')) {
    $addressAfter = aws ec2 describe-addresses --region $Region --allocation-ids $ExpectedAllocationId --output json | ConvertFrom-Json
    if ($addressAfter.Addresses[0].AssociationId) {
        throw "Refusing release: Elastic IP is still associated"
    }
    aws ec2 release-address --region $Region --allocation-id $ExpectedAllocationId
}

Write-Output "Verified and decommissioned exact instance $ExpectedInstanceId; no other AWS resource was targeted."
