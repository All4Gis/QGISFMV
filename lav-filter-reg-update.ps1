if (Test-Path "HKLM:\SOFTWARE\WOW6432Node\LAV\Splitter"){
  ""
  "HKLM:\SOFTWARE\WOW6432Node\LAV\Splitter updating QueueMaxPackets to 3000"
  $registryPath = "HKLM:\SOFTWARE\WOW6432Node\LAV\Splitter"
  $Name = "QueueMaxPackets"
  $value = "3000"
  New-ItemProperty -Path $registryPath -Name $name -Value $value -PropertyType DWORD -Force | Out-Null
}

New-PSDrive HKU Registry HKEY_USERS
$hkeyUsers = [Microsoft.Win32.RegistryKey]::OpenRemoteBaseKey('USERS', $env:COMPUTERNAME)
$hkeyUsersSubkeys = $hkeyUsers.GetSubKeyNames()
$hkeyUsersSubkeys | % {
    $runKey = "$_\Software\LAV\Splitter"       
    $runKeySubKey = $hkeyUsers.OpenSubKey($runKey)
    if ($runKeySubKey) {
      "$("HKEY_USERS:\$_\Software\LAV\Splitter") -- Key Found, updating QueueMaxPackets to 3000"
      $registryPath = $("HKU:\$_\Software\LAV\Splitter")
      $Name = "QueueMaxPackets"
      $value = "3000"
      New-ItemProperty -Path $registryPath -Name $name -Value $value -PropertyType DWORD -Force | Out-Null
    }
}

