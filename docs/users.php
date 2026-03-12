<?php
$caminho = 'http://187.45.181.94:1531/datasnap/rest/TDMServerM/';

// Timeout padrão para as requisições (em segundos)
$curlTimeout = 30;

// --- FUNÇÕES DE COMUNICAÇÃO ---

//** Executa uma query SQL no DataSnap usando o método 'ExecuteSQLMobile'.
// * @param string $sql A instrução SQL a ser executada.
// * @return array O resultado da consulta ou um array com uma chave 'error'.

function executarQuery(string $sql): array {
    global $caminho, $curlTimeout;

    $url = $caminho . 'ExecuteSQLMobile'; // Usando o nome da sua função
    $payload = ['SQLQuery' => $sql];
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($payload),
        CURLOPT_TIMEOUT        => $curlTimeout
    ]);

    $response_body = curl_exec($ch);
    if ($response_body === false) {
        error_log("executarQuery - cURL Error: " . curl_error($ch));
        return ['error' => 'Erro de comunicação com o servidor.'];
    }
    curl_close($ch);
    $decoded = json_decode($response_body, true);
    if (json_last_error() !== JSON_ERROR_NONE) {
        error_log("executarQuery - JSON Error: " . json_last_error_msg() . " Response: " . $response_body);
        return ['error' => 'Resposta do servidor em formato inválido.'];
    }
    if (isset($decoded['error'])) { return ['error' => $decoded['error']]; }


    // --- LÓGICA DE EXTRAÇÃO CORRIGIDA (do seu Global.php) ---
    if (isset($decoded['result'][0][0][0]) && is_array($decoded['result'][0][0][0])) {
        return $decoded['result'][0][0][0];
    }
    elseif (isset($decoded['result'][0]) && is_array($decoded['result'][0])) {
        return $decoded['result'][0];
    }
    elseif (is_array($decoded)) {
        return $decoded;
    }
    
    return [];
}


 $sqlLogin = "SELECT *  from VW_US_ATIVOS ";

$resultadoLogin = executarQuery($sqlLogin);

header('Content-Type: application/json');
echo json_encode($resultadoLogin);
?>