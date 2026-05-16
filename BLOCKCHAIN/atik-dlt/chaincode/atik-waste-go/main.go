package main

import (
	"encoding/json"
	"fmt"
	"strings"

	"github.com/hyperledger/fabric-contract-api-go/v2/contractapi"
)

// AtikWaste records JSON blobs under WASTE_{id} (same behavior as Node chaincode).
type AtikWaste struct {
	contractapi.Contract
}

func wasteKey(id string) string {
	return "WASTE_" + id
}

// CreateWaste stores jsonStr at WASTE_id.
func (a *AtikWaste) CreateWaste(ctx contractapi.TransactionContextInterface, id, jsonStr string) error {
	stub := ctx.GetStub()
	k := wasteKey(id)
	existing, err := stub.GetState(k)
	if err != nil {
		return err
	}
	if existing != nil && len(existing) > 0 {
		return fmt.Errorf("id already exists: %s", id)
	}
	return stub.PutState(k, []byte(jsonStr))
}

// ReadWaste returns raw JSON string.
func (a *AtikWaste) ReadWaste(ctx contractapi.TransactionContextInterface, id string) (string, error) {
	b, err := ctx.GetStub().GetState(wasteKey(id))
	if err != nil {
		return "", err
	}
	if b == nil || len(b) == 0 {
		return "", fmt.Errorf("not found: %s", id)
	}
	return string(b), nil
}

// SaveWaste replaces state with jsonStr.
func (a *AtikWaste) SaveWaste(ctx contractapi.TransactionContextInterface, id, jsonStr string) error {
	stub := ctx.GetStub()
	k := wasteKey(id)
	cur, err := stub.GetState(k)
	if err != nil {
		return err
	}
	if cur == nil || len(cur) == 0 {
		return fmt.Errorf("not found: %s", id)
	}
	return stub.PutState(k, []byte(jsonStr))
}

// DeleteWaste removes WASTE_id.
func (a *AtikWaste) DeleteWaste(ctx contractapi.TransactionContextInterface, id string) error {
	return ctx.GetStub().DelState(wasteKey(id))
}

// QueryAllWastes returns JSON array of objects (and raw fallback), matching Node chaincode.
func (a *AtikWaste) QueryAllWastes(ctx contractapi.TransactionContextInterface) (string, error) {
	stub := ctx.GetStub()
	it, err := stub.GetStateByRange("", "")
	if err != nil {
		return "", err
	}
	defer it.Close()

	out := make([]interface{}, 0)
	for it.HasNext() {
		q, err := it.Next()
		if err != nil {
			return "", err
		}
		if !strings.HasPrefix(q.Key, "WASTE_") {
			continue
		}
		var m map[string]interface{}
		if err := json.Unmarshal(q.Value, &m); err == nil {
			out = append(out, m)
		} else {
			out = append(out, map[string]interface{}{
				"id":  strings.TrimPrefix(q.Key, "WASTE_"),
				"raw": string(q.Value),
			})
		}
	}
	b, err := json.Marshal(out)
	if err != nil {
		return "", err
	}
	return string(b), nil
}

func main() {
	cc, err := contractapi.NewChaincode(&AtikWaste{})
	if err != nil {
		panic(err)
	}
	if err := cc.Start(); err != nil {
		panic(err)
	}
}
