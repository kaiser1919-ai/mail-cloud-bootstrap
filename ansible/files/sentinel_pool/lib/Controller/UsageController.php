<?php
declare(strict_types=1);
namespace OCA\SentinelPool\Controller;
use OCP\AppFramework\Controller;
use OCP\AppFramework\Http\DataResponse;
use OCP\AppFramework\Http\Attribute\NoAdminRequired;
use OCP\AppFramework\Http\Attribute\NoCSRFRequired;
use OCP\IRequest;
use OCP\IUserSession;
class UsageController extends Controller {
 public function __construct(string $appName, IRequest $request, private IUserSession $userSession) {parent::__construct($appName, $request);}
 #[NoAdminRequired]
 #[NoCSRFRequired]
 public function index(): DataResponse {
  $user = $this->userSession->getUser();
  if ($user === null || !$user->isEnabled()) {return $this->respond(['status' => 'unauthorized'], 401);}
  $path = '/run/mail-cloud-pool-usage/usage.json';
  if (is_link($path) || !is_file($path) || filesize($path) > 2048) {return $this->unavailable();}
  try {$row = json_decode((string)file_get_contents($path), true, 32, JSON_THROW_ON_ERROR);} catch (\Throwable) {return $this->unavailable();}
  if (!is_array($row) || ($row['status'] ?? '') !== 'ok' || !is_int($row['measured_at'] ?? null) || time() - $row['measured_at'] > 90 || $row['measured_at'] > time() + 5) {return $this->unavailable();}
  foreach (['total_bytes','used_bytes','available_bytes','reserved_bytes'] as $key) {
   if (!is_int($row[$key] ?? null) || $row[$key] < 0) {return $this->unavailable();}
  }
  if ($row['total_bytes'] <= 0 || $row['used_bytes'] + $row['available_bytes'] + $row['reserved_bytes'] !== $row['total_bytes']) {return $this->unavailable();}
  return $this->respond(['status' => 'ok', 'total_bytes' => $row['total_bytes'], 'used_bytes' => $row['used_bytes'], 'available_bytes' => $row['available_bytes'], 'reserved_bytes' => $row['reserved_bytes'], 'measured_at' => $row['measured_at'], 'refresh_seconds' => 30, 'max_delay_seconds' => 70]);
 }
 private function unavailable(): DataResponse {return $this->respond(['status'=>'unavailable'], 503);}
 private function respond(array $data, int $status = 200): DataResponse {
  $response = new DataResponse($data, $status);$response->addHeader('Cache-Control', 'no-store, private');return $response;
 }
}
